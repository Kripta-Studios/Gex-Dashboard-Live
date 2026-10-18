"""Physical NYSE minute clock for complete and early-close research sessions."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionClock:
    close_i: int = 390

    def __post_init__(self):
        if type(self.close_i) is not int or self.close_i not in (210, 390):
            raise ValueError("Only NYSE 13:00 and 16:00 session clocks are supported")

    @property
    def n_slots(self):
        return self.close_i + 1

    @property
    def first_state(self):
        return 60

    @property
    def last_state(self):
        return self.close_i - 15

    @property
    def eod_i(self):
        return self.close_i - 5

    @property
    def is_full(self):
        return self.close_i == 390

    def as_dict(self):
        return dict(
            close_i=self.close_i,
            n_slots=self.n_slots,
            first_state=self.first_state,
            last_state=self.last_state,
            eod_i=self.eod_i,
            time_unit_minutes=390,
        )


FULL = SessionClock(390)
SHORT = SessionClock(210)
