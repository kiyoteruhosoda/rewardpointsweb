"""家族まるごとの控え（アーカイブ）— バックアップと復元の受け渡し形（ADR-0026）。

家族・参加者・台帳・記録・毎日のボーナスを 1 つの入れ子で持つ。**アカウントは
入らない** — ログイン ID もパスワードも招待コードもここには現れない。復元した
家族に本人が入り直す道は招待コードで、控えの中身とは別に用意されている。

行どうしの繋がり（誰が記録したか、どの記録の打ち消し・訂正か）は、DB の ID では
なくファイルの中だけで通じる **ref**（``"m1"`` / ``"t1"``）で表す。復元先では ID が
すべて変わるため、書き出した ID をそのまま書けば必ず食い違う。ref なら別の
インスタンスへ持ち込んでも繋がりが保たれる。

``version`` は形が変わったときに上げる。読めない版は
:class:`~bounded_contexts.reward_points.domain.exceptions.UnsupportedArchiveVersionError`
で断る — 知らない項目を黙って捨てると、復元したつもりの家族から記録が消える。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from bounded_contexts.reward_points.domain.value_objects.family_role import FamilyRole

#: ファイルの種類。別のアプリの JSON を取り違えて渡されたときに気付くための印
ARCHIVE_FORMAT = "rewardpointsweb.family"

#: 書き出す形の版。形を変えたら上げる
ARCHIVE_VERSION = 2

#: 取り込める版。
#:
#: 版 1 との違いは家族のルール（``family_rules``）が載るかどうかだけで、無くても
#: 家族は元どおりに作り直せる（ADR-0027）。**すでに手元にある控えを読めなくしない**
#: ため、増えた項目が「無くても復元が成立する」ものである限り、古い版も受け付ける。
#: 記録に関わる形が変わったときは、この集合から外して断る。
SUPPORTED_ARCHIVE_VERSIONS = frozenset({1, ARCHIVE_VERSION})


@dataclass(frozen=True, kw_only=True)
class ArchivedTransactionDTO:
    """台帳の 1 行。"""

    #: このファイルの中でこの行を指す名前（台帳の中で一意）
    ref: str
    amount: int
    reason: str
    occurred_at: datetime
    #: 記録した参加者の ref。毎日のボーナス（ADR-0024）と、家族を離れた人の行では None
    granted_by: str | None
    #: 打ち消しの行なら、打ち消した相手の ref（ADR-0010）
    reverses: str | None
    #: 訂正後の行なら、言い直した相手の ref（ADR-0022）
    corrects: str | None


@dataclass(frozen=True, kw_only=True)
class ArchivedDailyBonusDTO:
    """毎日のボーナスの約束（ADR-0024）。

    ``granted_through`` も控える。落とすと、復元した直後に「まだ渡していない日」
    が開始日まで遡って復活し、すでに控えに入っている行と同じ日のボーナスが
    もう一度足される。
    """

    amount: int
    reason: str
    starts_on: date
    granted_through: date | None


@dataclass(frozen=True, kw_only=True)
class ArchivedLedgerDTO:
    #: 書いた順（古い行が先）。打ち消し・訂正は必ず相手より後に並ぶ
    transactions: tuple[ArchivedTransactionDTO, ...]
    daily_bonus: ArchivedDailyBonusDTO | None


@dataclass(frozen=True, kw_only=True)
class ArchivedMemberDTO:
    """家族への参加。誰のアカウントだったかは持たない。"""

    ref: str
    display_name: str
    role: FamilyRole
    #: 台帳を持つのは ``role = child`` だけ（ADR-0009）
    ledger: ArchivedLedgerDTO | None


@dataclass(frozen=True, kw_only=True)
class FamilyArchiveDTO:
    format: str
    version: int
    exported_at: datetime
    family_name: str
    #: 家族で決めた約束ごと（ADR-0027）。書いていなければ None。版 1 の控えには無い
    family_rules: str | None
    #: 画面に並ぶ順（owner が先、次に親、最後に家族が決めた順の子）
    members: tuple[ArchivedMemberDTO, ...]


@dataclass(frozen=True, kw_only=True)
class ImportedFamilyDTO:
    """取り込みの結果。数を返すのは、復元できた量を人が確かめられるようにするため。"""

    family_id: int
    name: str
    member_count: int
    transaction_count: int


__all__ = [
    "ARCHIVE_FORMAT",
    "ARCHIVE_VERSION",
    "SUPPORTED_ARCHIVE_VERSIONS",
    "ArchivedDailyBonusDTO",
    "ArchivedLedgerDTO",
    "ArchivedMemberDTO",
    "ArchivedTransactionDTO",
    "FamilyArchiveDTO",
    "ImportedFamilyDTO",
]
