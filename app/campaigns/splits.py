from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Period:
    start: date
    end: date


@dataclass(frozen=True)
class TemporalSplit:
    train: Period
    validation: Period
    test: Period

    def as_dict(self) -> dict[str, dict[str, str]]:
        return {
            "train": _period_dict(self.train),
            "validation": _period_dict(self.validation),
            "test": _period_dict(self.test),
        }


def build_temporal_split(
    start_date: date,
    end_date: date,
    split_definition: dict[str, dict[str, str]] | None,
) -> TemporalSplit:
    if split_definition:
        split = TemporalSplit(
            train=_parse_period(split_definition["train"]),
            validation=_parse_period(split_definition["validation"]),
            test=_parse_period(split_definition["test"]),
        )
    else:
        days = (end_date - start_date).days
        if days < 6:
            raise ValueError("campaign period must span at least 6 days")
        train_end = start_date.fromordinal(start_date.toordinal() + max(2, int(days * 0.6)))
        validation_end = start_date.fromordinal(start_date.toordinal() + max(4, int(days * 0.8)))
        split = TemporalSplit(
            train=Period(start_date, train_end),
            validation=Period(train_end, validation_end),
            test=Period(validation_end, end_date),
        )
    validate_temporal_split(split, start_date, end_date)
    return split


def validate_temporal_split(split: TemporalSplit, start_date: date, end_date: date) -> None:
    periods = [split.train, split.validation, split.test]
    if any(period.start >= period.end for period in periods):
        raise ValueError("each temporal split period must have start before end")
    if split.train.start < start_date or split.test.end > end_date:
        raise ValueError("split periods must stay inside the campaign period")
    if not (split.train.end <= split.validation.start and split.validation.end <= split.test.start):
        raise ValueError("temporal split periods must not overlap")


def _parse_period(raw: dict[str, str]) -> Period:
    return Period(start=date.fromisoformat(raw["start"]), end=date.fromisoformat(raw["end"]))


def _period_dict(period: Period) -> dict[str, str]:
    return {"start": period.start.isoformat(), "end": period.end.isoformat()}
