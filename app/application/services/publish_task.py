import asyncio
import json
import logging
import os
import random
import time
from collections import defaultdict
from itertools import zip_longest
from typing import Optional

from sqlalchemy.orm import Session

from app.application.services.caption_uniqualizer import CaptionUniqualizerService
from app.application.services.uniqalize_reel import ReelsUniqalizerService
from app.domain.entities import GroupType, Reel, SocialType, UserGroup
from app.domain.models import AccountResultStatus, Folder, InstagramAccount, PublishTask, SmmboxAccount, TaskAccountResult, TaskStage, TaskStatus
from app.domain.repositories import CombinedPublisher, InstagramPublisher


class PublishVideoTask:
    def __init__(
        self,
        uniqalizer: ReelsUniqalizerService,
        instagram_publisher: InstagramPublisher,
        caption_uniqualizer: Optional[CaptionUniqualizerService] = None,
        smmbox_client: Optional[CombinedPublisher] = None,
    ):
        self.uniqalizer = uniqalizer
        self.instagram_publisher = instagram_publisher
        self.caption_uniqualizer = caption_uniqualizer
        self.smmbox_client = smmbox_client
        self.logger = logging.getLogger(__name__)

    def _build_publish_groups(
        self,
        instagram_accounts: list[InstagramAccount],
        smmbox_groups: list[UserGroup],
    ) -> list[list[tuple]]:
        """
        Объединяет Instagram-аккаунты и SMMBox-группы в публикационные группы.
        В каждой группе — максимум 1 аккаунт каждого типа соцсети.
        Возвращает список групп, каждая группа — список кортежей ('instagram', account) | ('smmbox', group).
        """
        buckets: dict[SocialType, list[tuple]] = defaultdict(list)

        for acc in instagram_accounts:
            buckets[SocialType.INSTAGRAM].append(('instagram', acc))

        for g in smmbox_groups:
            buckets[g.social].append(('smmbox', g))

        groups = []
        for items in zip_longest(*buckets.values()):
            group = [item for item in items if item is not None]
            groups.append(group)

        return groups

    def _uniqualize_caption(self, caption: str) -> str:
        if self.caption_uniqualizer and caption:
            try:
                return self.caption_uniqualizer.uniqualize(caption)
            except Exception:
                self.logger.exception("Caption uniqualization failed, using original")
        return caption

    def execute(self, task: PublishTask, db: Session):
        temp_path = task.file_path
        caption = task.caption
        try:
            task.stage = TaskStage.writing
            task.status = TaskStatus.processing
            db.commit()

            # --- Получаем Instagram-аккаунты ---
            if task.selected_account_ids:
                ids = json.loads(task.selected_account_ids)
                instagram_accounts = db.query(InstagramAccount).filter(InstagramAccount.id.in_(ids)).all()
            else:
                instagram_accounts = db.query(InstagramAccount).join(Folder).where(Folder.id == task.folder_id).all()

            # --- Получаем SMMBox-аккаунты из БД для данной папки ---
            smmbox_groups: list[UserGroup] = []
            if self.smmbox_client:
                smmbox_db = db.query(SmmboxAccount).filter_by(folder_id=task.folder_id).all()
                smmbox_groups = [
                    UserGroup(
                        id=a.smmbox_id,
                        social=SocialType(a.social),
                        type=GroupType(a.type),
                        name=a.name,
                    )
                    for a in smmbox_db
                ]

            # --- Строим публикационные группы ---
            publish_groups = self._build_publish_groups(instagram_accounts, smmbox_groups)

            if not publish_groups:
                raise Exception("Нет аккаунтов для публикации")

            task.stage = TaskStage.processing
            db.commit()

            # Уникализируем по 1 видео на каждую группу
            urls = self.uniqalizer.execute(temp_path, len(publish_groups))
            self.logger.info("Urls of videos in s3: %s", urls)

            is_trial = bool(task.is_test_mode)

            task.stage = TaskStage.uploading
            db.commit()

            for i, (url, group) in enumerate(zip(urls, publish_groups)):
                unique_caption = self._uniqualize_caption(caption)
                reel = Reel(url, unique_caption, is_trial=is_trial)

                # Собираем SMMBox-группы этой publish-группы для батч-вызова
                smmbox_items: list[UserGroup] = []

                for (source, item) in group:
                    if source == 'instagram':
                        account: InstagramAccount = item
                        try:
                            media_id = asyncio.run(self.instagram_publisher.publish_reel(reel, account))
                            ar = TaskAccountResult(
                                task_id=task.id,
                                account_id=account.id,
                                status=AccountResultStatus.success,
                                media_id=media_id,
                            )
                        except Exception as e:
                            self.logger.exception("Instagram publish failed for account %s", account.instagram_id, exc_info=e)
                            ar = TaskAccountResult(
                                task_id=task.id,
                                account_id=account.id,
                                status=AccountResultStatus.failed,
                                error=str(e),
                            )
                        db.add(ar)
                        db.commit()

                    elif source == 'smmbox':
                        smmbox_items.append(item)

                if smmbox_items:
                    try:
                        self.smmbox_client.publish_reel(reel, smmbox_items)
                        self.logger.info("SMMBox publish OK for groups: %s", [g.id for g in smmbox_items])
                    except Exception:
                        self.logger.exception("SMMBox publish failed for groups %s", [g.id for g in smmbox_items])

                if i < len(publish_groups) - 1:
                    delay = random.randint(60, 120)
                    self.logger.info("Sleeping %ds before next group", delay)
                    time.sleep(delay)

            task.status = TaskStatus.completed
            task.stage = TaskStage.done
            db.commit()

        except Exception as e:
            if task:
                task.status = TaskStatus.failed
                task.error = str(e)
                db.commit()
            self.logger.exception("Publish video task exception", e)
        finally:
            db.close()
            if os.path.exists(temp_path):
                os.remove(temp_path)
