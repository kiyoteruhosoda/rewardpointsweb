"""家族まるごとを控えとして書き出す（ADR-0026）。

バックアップのための操作なので、返すのは「その家族の全部」— 参加者も、子どもの
台帳も、毎日のボーナスの約束も入る。閲覧者ごとの出し分けはしないため、届いて
よい相手を先に絞る。**親（owner / parent）だけ**が呼べる。子は自分の台帳しか
見られない（ADR-0009）ので、家族全員分が載る控えは渡せない。

アカウントは載せない（``FamilyArchiveDTO``）。控えが漏れても、そこからログイン
できる情報は出てこない。
"""

from __future__ import annotations

from bounded_contexts.reward_points.application.dto.family_archive_dto import FamilyArchiveDTO
from bounded_contexts.reward_points.application.family_access_resolver import FamilyAccessResolver
from bounded_contexts.reward_points.application.family_archive_writer import FamilyArchiveWriter


class ExportFamilyUseCase:
    def __init__(self, access: FamilyAccessResolver, writer: FamilyArchiveWriter) -> None:
        self._access = access
        self._writer = writer

    def execute(self, *, family_id: int, account_id: int) -> FamilyArchiveDTO:
        self._access.require_guardian(family_id=family_id, account_id=account_id)
        return self._writer.write(family_id)


__all__ = ["ExportFamilyUseCase"]
