"""UC9 SavingsReportRepository — header + line CRUD for the savings report tables."""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.models import (
    DailySavingsReportLineModel,
    DailySavingsReportModel,
)


class SavingsReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_no_commit(
        self,
        header: DailySavingsReportModel,
        lines: list[DailySavingsReportLineModel],
    ) -> None:
        """Add header + lines; flush so PKs/FKs propagate; caller commits."""
        self.db.add(header)
        self.db.flush()
        for line in lines:
            line.report_id = header.id
            self.db.add(line)
        self.db.flush()

    def get_for_building_date(
        self, building_id: int, report_date: date
    ) -> DailySavingsReportModel | None:
        return (
            self.db.execute(
                select(DailySavingsReportModel).where(
                    DailySavingsReportModel.building_id == building_id,
                    DailySavingsReportModel.report_date == report_date,
                )
            )
            .scalars()
            .first()
        )

    def lines_for_report(
        self, report_id: int
    ) -> list[DailySavingsReportLineModel]:
        return list(
            self.db.execute(
                select(DailySavingsReportLineModel)
                .where(DailySavingsReportLineModel.report_id == report_id)
                .order_by(DailySavingsReportLineModel.id.asc())
            )
            .scalars()
            .all()
        )

    def count_reports_for(
        self, building_id: int, report_date: date
    ) -> int:
        return int(
            self.db.execute(
                select(func.count(DailySavingsReportModel.id)).where(
                    DailySavingsReportModel.building_id == building_id,
                    DailySavingsReportModel.report_date == report_date,
                )
            ).scalar()
            or 0
        )

    def count_lines_for(
        self, building_id: int, report_date: date
    ) -> int:
        return int(
            self.db.execute(
                select(func.count(DailySavingsReportLineModel.id))
                .join(
                    DailySavingsReportModel,
                    DailySavingsReportLineModel.report_id
                    == DailySavingsReportModel.id,
                )
                .where(
                    DailySavingsReportModel.building_id == building_id,
                    DailySavingsReportModel.report_date == report_date,
                )
            ).scalar()
            or 0
        )
