# -*- coding: utf-8 -*-

from django.db import models
from django.conf import settings
from django.utils.translation import ugettext as _
from django.utils.timezone import localtime
from model_utils.models import TimeStampedModel, SoftDeletableModel, SoftDeletableManager
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth import get_user_model
import dataclasses
import uuid
import datetime
from typing import Optional, Any
from django.db.models import Q

UserModel: AbstractBaseUser = get_user_model()


@dataclasses.dataclass(frozen=True)
class DialogUser:
    id: uuid
    was_online: Optional[datetime.datetime]
    is_online: bool = False


@dataclasses.dataclass(frozen=True)
class Dialog:
    id: str
    creator: DialogUser
    opponent: DialogUser

    def __eq__(self, other) -> bool:
        return (self.creator.id == other.opponent.id and self.opponent.id == other.creator.id) or (
            self.creator.id == other.creator.id and self.opponent.id == other.opponent.id)


@dataclasses.dataclass(frozen=True)
class Message:
    dialog_id: str
    msg_id: int
    data: bytes
    sent_by: DialogUser
    sent_at: datetime.datetime
    was_read: bool


@dataclasses.dataclass(frozen=True)
class TextMessage(Message):
    data: str


def user_directory_path(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return f"user_{instance.sender.pk}/{filename}"


class DialogsModel(TimeStampedModel):
    id = models.BigAutoField(primary_key=True, verbose_name=_("Id"))
    user1 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("User1"),
                              related_name="+", db_index=True)
    user2 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("User2"),
                              related_name="+", db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user1', 'user2'], name='Unique dialog')
        ]
        verbose_name = _("Dialog")
        verbose_name_plural = _("Dialogs")

    def __str__(self):
        return _("Dialog between ") + f"{self.user1.pk}, {self.user2.pk}"

    @staticmethod
    def dialog_exists(u1: AbstractBaseUser, u2: AbstractBaseUser) -> Optional[Any]:
        return DialogsModel.objects.filter(Q(user1=u1, user2=u2) | Q(user1=u2, user2=u1)).first()

    @staticmethod
    def create_if_not_exists(u1: AbstractBaseUser, u2: AbstractBaseUser):
        res = DialogsModel.dialog_exists(u1, u2)
        if not res:
            DialogsModel.objects.create(user1=u1, user2=u2)

    @staticmethod
    def get_dialogs_for_user(user: AbstractBaseUser):
        return DialogsModel.objects.filter(Q(user1=user) | Q(user2=user)).values_list('user1__pk', 'user2__pk')

class MessageModel(TimeStampedModel, SoftDeletableModel):
    id = models.BigAutoField(primary_key=True, verbose_name=_("Id"))
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Author"),
                               related_name='from_user', db_index=True)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name=_("Recipient"),
                                  related_name='to_user', db_index=True)
    text = models.TextField(verbose_name=_("Text"), blank=True)
    file = models.FileField(verbose_name=_("File"), blank=True, upload_to=user_directory_path)

    read = models.BooleanField(verbose_name=_("Read"), default=False)
    all_objects = models.Manager()

    @staticmethod
    def get_unread_count_for_dialog_with_user(sender, recipient):
        return MessageModel.objects.filter(sender_id=sender, recipient_id=recipient, read=False).count()

    def get_create_localtime(self):
        return localtime(self.created)

    def __str__(self):
        return str(self.pk)

    def save(self, *args, **kwargs):
        super(MessageModel, self).save(*args, **kwargs)
        return DialogsModel.create_if_not_exists(self.sender, self.recipient)

    class Meta:
        ordering = ('-created',)
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")

# TODO:
# Possible features - update with pts
# was_online field for User (1to1 model)
# read_at - timestamp