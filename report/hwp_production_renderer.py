"""Production HWP renderer for the approved report front and all targets.

The renderer creates a transient A4 HTML representation and asks Hangul COM to
import and save it as HWP.  The HTML is never a deliverable and is always removed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any, Callable

from .hwp_adapter import HwpAdapterError, HwpComUnavailableError, _default_com_factory
from .production_model import ProductionInspectionItemView, ProductionReportView
from .production_page_plan import (
    ProductionPagePlan,
    plan_production_pages,
)
from .production_view import validate_customer_visible_text


NAVY = "#17375E"
BLUE = "#2C5F8A"
PALE = "#EAF0F6"
INK = "#263442"
MID = "#667788"
LINE = "#B8C3CE"


@dataclass
class ProductionHwpResult:
    output_path: str
    page_count: int
    pdf_preview_path: str = ""
    warnings: list[str] = field(default_factory=list)


def _safe(value) -> str:
    return escape("" if value is None else str(value)).replace("\n", "<br>")


def _image_source(path: str) -> str:
    """Use the local path form accepted by Hangul's HTML importer."""
    return escape(str(Path(path).resolve()).replace("\\", "/"), quote=True)


class HwpProductionRenderer:
    """Create the production-report front and target pages without legacy templates."""

    def __init__(self, com_factory: Callable[[], Any] | None = None):
        self._com_factory = com_factory or _default_com_factory

    @staticmethod
    def _trace(message: str) -> None:
        trace_path = os.environ.get("HWP_PRODUCTION_TRACE_LOG", "").strip()
        if not trace_path:
            return
        with open(trace_path, "a", encoding="utf-8") as trace_file:
            trace_file.write(f"{time.monotonic():.3f} {message}\n")
            trace_file.flush()

    @staticmethod
    def _set_visibility(hwp: Any, visible: bool) -> None:
        try:
            hwp.XHwpWindows.Item(0).Visible = visible
        except Exception:
            pass

    @classmethod
    def _prepare_automation(cls, hwp: Any) -> None:
        for module_name in (
            "FilePathCheckerModuleExample",
            "FilePathCheckerModule",
        ):
            try:
                if hwp.RegisterModule("FilePathCheckDLL", module_name):
                    cls._trace("security module registered")
                    break
            except Exception:
                continue
        try:
            hwp.SetMessageBoxMode(0x00010000)
            cls._trace("message box mode configured")
        except Exception:
            cls._trace("message box mode unavailable")

    @staticmethod
    def _close(hwp: Any) -> None:
        try:
            hwp.Clear(1)
        except Exception:
            pass

    @staticmethod
    def _quit(hwp: Any) -> None:
        try:
            hwp.Quit()
        except Exception:
            pass

    def generate(
        self,
        view: ProductionReportView,
        output_path: str | os.PathLike[str],
        *,
        visible: bool = False,
        pdf_preview_path: str | os.PathLike[str] | None = None,
    ) -> ProductionHwpResult:
        validate_customer_visible_text(view)
        output = Path(output_path).resolve()
        if not output.parent.is_dir():
            raise HwpAdapterError(f"출력 폴더가 없습니다: {output.parent}")
        if output.suffix.lower() != ".hwp":
            raise HwpAdapterError("정식 결과보고서 출력 확장자는 .hwp여야 합니다")
        preview = Path(pdf_preview_path).resolve() if pdf_preview_path else None
        if preview and not preview.parent.is_dir():
            raise HwpAdapterError(f"PDF 비교본 출력 폴더가 없습니다: {preview.parent}")

        page_plan = plan_production_pages(view)
        html_text = self._build_html(view, page_plan)
        page_count = page_plan.total_page_count
        style_match = re.search(r"<style>(.*?)</style>", html_text, re.DOTALL)
        body_match = re.search(r"<body>(.*?)</body>", html_text, re.DOTALL)
        if not style_match or not body_match:
            raise HwpAdapterError("정식 보고서 임시 페이지 구조가 올바르지 않습니다")
        page_bodies = body_match.group(1).split("<!--PRODUCTION_PAGE_BREAK-->")
        temporary_pages: list[Path] = []
        for page_index, page_body in enumerate(page_bodies, 1):
            handle, html_name = tempfile.mkstemp(
                prefix=f".{output.stem}_{page_index:03d}_",
                suffix=".html",
                dir=output.parent,
            )
            os.close(handle)
            temporary_page = Path(html_name)
            page_document = (
                "<html><head><meta http-equiv='Content-Type' content='text/html; charset=euc-kr'><style>"
                + style_match.group(1)
                + "</style></head><body>"
                + page_body
                + "</body></html>"
            )
            temporary_page.write_bytes(
                page_document.encode("cp949", errors="xmlcharrefreplace")
            )
            temporary_pages.append(temporary_page)
        hwp = None
        try:
            self._trace("COM create start")
            hwp = self._com_factory()
            self._trace("COM create complete")
            self._set_visibility(hwp, visible)
            self._prepare_automation(hwp)
            self._trace("HTML open 1 start")
            opened = hwp.Open(str(temporary_pages[0]), "HTML", "")
            self._trace("HTML open 1 complete")
            if opened is False:
                raise HwpAdapterError("한글에서 임시 A4 보고서를 열지 못했습니다")
            for page_index, temporary_page in enumerate(temporary_pages[1:], 2):
                self._trace(f"HTML insert {page_index}/{page_count} start")
                try:
                    hwp.MovePos(3, 0, 0)
                except Exception as error:
                    raise HwpAdapterError("한글 문서 끝으로 이동하지 못했습니다") from error
                if hwp.HAction.Run("BreakPage") is False:
                    raise HwpAdapterError("정식 보고서 페이지 나눔 삽입에 실패했습니다")
                if hwp.Insert(str(temporary_page), "HTML", "") is False:
                    raise HwpAdapterError("정식 보고서 페이지 삽입에 실패했습니다")
                self._trace(f"HTML insert {page_index}/{page_count} complete")
            self._trace("HWP save start")
            saved = hwp.SaveAs(str(output), "HWP", "")
            self._trace("HWP save complete")
            if saved is False:
                raise HwpAdapterError("정식 HWP 저장에 실패했습니다")
            if not output.is_file() or output.stat().st_size <= 0:
                raise HwpAdapterError("생성된 정식 HWP 파일이 없거나 비어 있습니다")
            preview_value = ""
            if preview:
                self._trace("PDF save start")
                converted = hwp.SaveAs(str(preview), "PDF", "")
                self._trace("PDF save complete")
                if converted is False or not preview.is_file() or preview.stat().st_size <= 0:
                    raise HwpAdapterError("시각 비교용 PDF 변환에 실패했습니다")
                preview_value = str(preview)
            return ProductionHwpResult(
                output_path=str(output),
                page_count=page_count,
                pdf_preview_path=preview_value,
                warnings=list(view.warnings),
            )
        except (HwpAdapterError, HwpComUnavailableError, OSError):
            raise
        except Exception as error:
            raise HwpAdapterError(f"정식 HWP 생성 실패: {error}") from error
        finally:
            if hwp is not None:
                self._trace("Clear start")
                self._close(hwp)
                self._trace("Clear complete")
                self._trace("Quit start")
                self._quit(hwp)
                self._trace("Quit complete")
            for temporary_page in temporary_pages:
                temporary_page.unlink(missing_ok=True)

    def _build_html(self, view: ProductionReportView, page_plan: ProductionPagePlan) -> str:
        pages: list[str] = []
        planned_total = page_plan.total_page_count

        def page(title: str, body: str, page_no: int, kicker: str = "") -> str:
            return f"""
<div class="page">
  <table class="pageheader"><tr><td><b>{_safe(title)}</b></td><td class="right">{_safe(view.site.site_name)}</td></tr></table>
  <div class="main"><div class="kicker">{_safe(kicker)}</div>{body}</div>
  <table class="pagefooter"><tr><td>{_safe(view.company.company_name)} | 기계설비 성능점검 결과보고서</td><td class="right">{page_no} / {planned_total}</td></tr></table>
</div>"""

        pages.append(self._cover(view))
        front = [
            ("보고서를 제출하며", self._greeting(view), "GREETING"),
            ("기계설비 성능점검 개요", self._general_overview(view), "REPORT OVERVIEW"),
            ("회사 및 보고서 기본정보", self._company(view), "COMPANY PROFILE"),
            ("기계설비성능점검업 등록정보", self._registration(view), "REGISTRATION"),
            ("목차", self._contents(), "CONTENTS"),
        ]
        general_topics = [
            ("성능점검의 목적", "설비 상태와 운전성능을 확인하고 유지관리 및 개선에 필요한 기술자료를 제공합니다."),
            ("성능점검 대상", "장비대장과 현장 설치상태를 대조하여 점검대상을 확정합니다."),
            ("자료 확인", "현황표, 설계도서, 유지관리 기록, 검사증 및 시험성적서를 확인합니다."),
            ("육안 확인", "외관·설치·운전상태와 누수·부식·손상 등 이상징후를 확인합니다."),
            ("작동시험", "안전조건과 운전조건이 확보된 경우 제어·경보·보호기능을 확인합니다."),
            ("계측 및 비교", "설계값·정격값·제조사 기준과 측정값을 구분하여 기록합니다."),
            ("점검결과 판정", "세부 점검기준 수행결과와 기술적소견을 근거로 최종판정을 기록합니다."),
            ("시스템 검토", "설비 간 연계, 운전·제어, 자료보유와 확인필요 사항을 종합 검토합니다."),
            ("에너지 검토", "관리주체 제공자료를 기준으로 에너지원별 연도 추세와 변화원인을 검토합니다."),
            ("결과 활용", "점검결과는 유지관리, 보수, 성능개선 및 중장기 계획의 기초자료로 활용합니다."),
        ]
        for title, body, kicker in front:
            pages.append(page(title, body, len(pages) + 1, kicker))
        for title, description in general_topics:
            pages.append(page(title, self._topic(description), len(pages) + 1, "PART 1 · GENERAL"))
        pages.append(page("기계설비 성능점검 결과보고서", self._result_form(view), 17, "PART 2 · RESULT FORM 01"))
        pages.append(page("점검결과 내역서", self._result_details(view), 18, "PART 2 · RESULT FORM 02"))

        for target_plan in page_plan.target_plans:
            target = view.targets[target_plan.target_index]
            item_chunks = [
                list(target.items[start:stop])
                for start, stop in target_plan.inspection_item_ranges
            ]
            for index, items in enumerate(item_chunks):
                title = f"기계설비 성능점검표 - {target.equipment_type} {target.management_no}"
                if index:
                    title += " (계속)"
                pages.append(page(title, self._inspection_table(target, items, index == 0), len(pages) + 1, "PART 3 · PERFORMANCE INSPECTION"))
            detail_chunks = [
                list(target.items[start:stop])
                for start, stop in target_plan.detail_item_ranges
            ]
            for items in detail_chunks:
                pages.append(page(
                    f"점검항목별 상세 검토 - {target.equipment_type} {target.management_no}",
                    self._detail_items(items), len(pages) + 1,
                    "PART 3 · ITEM DETAIL + PHOTO",
                ))

        for start, stop in page_plan.system_summary_ranges:
            pages.append(page(
                "기계설비 성능점검 시 검토사항 - 시스템검토 요약",
                self._system_summary(view, start, stop), len(pages) + 1,
                "PART 4 · SYSTEM REVIEW SUMMARY",
            ))
        for start, stop in page_plan.document_review_ranges:
            pages.append(page(
                "자료보유 및 확인사항",
                self._document_review(view, start, stop), len(pages) + 1,
                "PART 4 · DOCUMENT REVIEW",
            ))
        for start, stop in page_plan.operation_review_ranges:
            pages.append(page(
                "작동상태 및 운전검토",
                self._operation_review(view, start, stop), len(pages) + 1,
                "PART 4 · OPERATION REVIEW",
            ))
        for start, stop in page_plan.aging_ranges:
            pages.append(page(
                "내구연수에 따른 노후도 분석",
                self._aging_review(view, start, stop), len(pages) + 1,
                "PART 5 · AGING ANALYSIS",
            ))
        for start, stop in page_plan.improvement_ranges:
            pages.append(page(
                "성능개선계획",
                self._improvement_review(view, start, stop), len(pages) + 1,
                "PART 5 · IMPROVEMENT PLAN",
            ))

        css = f"""
@page {{ size: A4; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; color: {INK}; font-family: 'Malgun Gothic'; }}
.page {{ padding: 7mm 10mm 7mm; position: relative; background: white; }}
.pageheader, .pagefooter {{ width: 100%; border-collapse: collapse; }} .pageheader td {{ color:{NAVY}; font-size:8pt; border:0; border-bottom:1.2pt solid {NAVY}; padding:1mm 0 2mm; }} .pagefooter td {{ color:{MID}; font-size:7pt; border:0; border-top:.7pt solid {LINE}; padding:2mm 0 0; }} .right {{ text-align:right; }}
.main {{ padding-top: 8mm; min-height: 245mm; }}
.kicker {{ color: {BLUE}; font-size: 8pt; font-weight: bold; margin-bottom: 3mm; }}
.title {{ color: {INK}; font-size: 18pt; font-weight:bold; margin: 0 0 6mm; border-bottom: 2pt solid {NAVY}; padding-bottom: 3mm; }}
.subtitle {{ color: {NAVY}; font-size: 10pt; font-weight:bold; margin: 3mm 0 2mm; }} p {{ font-size: 9pt; line-height: 1.65; margin: 0 0 4mm; }}
.cover {{ padding:45mm 25mm 20mm; color:{INK}; }} .cover-title {{ color:{NAVY}; font-size:28pt; font-weight:bold; margin-top:25mm; border-top:10pt solid {NAVY}; padding-top:18mm; }} .cover .site {{ font-size:16pt; margin-top:14mm; color:{INK}; }} .cover .company {{ margin-top:90mm; font-size:13pt; color:{NAVY}; }}
.box {{ background:{PALE}; border-left:4pt solid {BLUE}; padding:5mm; margin:4mm 0; }}
table {{ width:100%; border-collapse:collapse; table-layout:fixed; margin:3mm 0; }} th {{ background:{NAVY}; color:white; font-size:7.6pt; padding:2.2mm 1.5mm; border:.5pt solid {LINE}; }} td {{ font-size:7.4pt; line-height:1.35; padding:2mm 1.5mm; border:.5pt solid {LINE}; vertical-align:middle; word-break:break-all; }}
.result th:nth-child(1){{width:18%}} .result th:nth-child(2){{width:15%}} .result th:nth-child(3){{width:22%}}
.inspection th:nth-child(1){{width:5%}} .inspection th:nth-child(2){{width:13%}} .inspection th:nth-child(3){{width:14%}} .inspection th:nth-child(4){{width:20%}} .inspection th:nth-child(5){{width:11%}} .inspection th:nth-child(6){{width:11%}} .inspection th:nth-child(7){{width:9%}} .inspection th:nth-child(8){{width:17%}}
.system-summary th:nth-child(1){{width:17%}} .system-summary th:nth-child(2){{width:23%}} .system-summary th:nth-child(3){{width:35%}} .system-summary th:nth-child(4){{width:25%}}
.document-review th:nth-child(1){{width:38%}} .document-review th:nth-child(2){{width:12%}} .document-review th:nth-child(3){{width:25%}} .document-review th:nth-child(4){{width:25%}}
.operation-review th:nth-child(1){{width:12%}} .operation-review th:nth-child(2){{width:17%}} .operation-review th:nth-child(3){{width:16%}} .operation-review th:nth-child(4){{width:10%}} .operation-review th:nth-child(5){{width:27%}} .operation-review th:nth-child(6){{width:18%}}
.aging-review th:nth-child(1){{width:17%}} .aging-review th:nth-child(2){{width:12%}} .aging-review th:nth-child(3){{width:12%}} .aging-review th:nth-child(4){{width:14%}} .aging-review th:nth-child(5){{width:12%}} .aging-review th:nth-child(6){{width:13%}} .aging-review th:nth-child(7){{width:20%}}
.improvement-review th:nth-child(1){{width:13%}} .improvement-review th:nth-child(2){{width:15%}} .improvement-review th:nth-child(3){{width:22%}} .improvement-review th:nth-child(4){{width:25%}} .improvement-review th:nth-child(5){{width:17%}} .improvement-review th:nth-child(6){{width:8%}}
.equipment td {{ background:{PALE}; font-size:8pt; }}
.detail {{ border:1pt solid {LINE}; padding:3mm; margin-bottom:4mm; min-height:58mm; }} .detail-grid {{ width:100%; }}
.photo {{ max-width:70mm; max-height:35mm; object-fit:contain; border:1pt solid {LINE}; }} .muted {{ color:{MID}; font-size:7pt; }}
"""
        if len(pages) != page_plan.total_page_count:
            raise HwpAdapterError(
                f"페이지 계획과 렌더링 결과가 다릅니다: 계획 {page_plan.total_page_count}, 생성 {len(pages)}"
            )
        return "<!doctype html><html><head><meta charset='utf-8'><style>" + css + "</style></head><body>" + "<!--PRODUCTION_PAGE_BREAK-->".join(pages) + "</body></html>"

    @staticmethod
    def _cover(view: ProductionReportView) -> str:
        return f"<div class='cover'><p class='cover-title'>기계설비 성능점검<br>결과보고서</p><div class='site'>{_safe(view.site.site_name) or 'TEST 현장'}</div><div class='company'>{_safe(view.company.company_name)}</div></div>"

    @staticmethod
    def _greeting(view):
        return f"<div class='title'>보고서를 제출하며</div><p>{_safe(view.site.site_name)}의 기계설비 성능점검 결과를 제출합니다.</p><div class='box'><p>현장점검, 계측 및 관련 자료 검토를 바탕으로 점검결과와 기술적 검토사항을 정리했습니다.</p></div>"

    @staticmethod
    def _general_overview(view):
        return f"<div class='title'>기계설비 성능점검 일반사항</div><table><tr><th>구분</th><th>내용</th></tr><tr><td>대상 건축물</td><td>{_safe(view.site.site_name)}</td></tr><tr><td>주소</td><td>{_safe(view.site.address)}</td></tr><tr><td>관리주체</td><td>{_safe(view.site.management_entity)}</td></tr><tr><td>점검기간</td><td>{_safe(view.site.inspection_period)}</td></tr></table>"

    @staticmethod
    def _company(view):
        c = view.company
        return f"<div class='title'>{_safe(c.company_name)}</div><div class='box'><p>{_safe(c.introduction)}</p></div><table><tr><th>주소</th><td>{_safe(c.address)}</td></tr><tr><th>연락처</th><td>{_safe(c.telephone)}</td></tr><tr><th>이메일</th><td>{_safe(c.email)}</td></tr></table>"

    @staticmethod
    def _registration(view):
        return f"<div class='title'>기계설비성능점검업 등록정보</div><div class='box'><p>등록증 원본은 Git 외부 로컬 자산에서 연결합니다.</p></div><table><tr><th>업체</th><td>{_safe(view.company.company_name)}</td></tr><tr><th>등록번호</th><td>{_safe(view.company.registration_no)}</td></tr><tr><th>책임기술자</th><td>{_safe(view.company.responsible_engineer)}</td></tr></table>"

    @staticmethod
    def _contents():
        rows = [("PART 1", "기계설비 성능점검 일반사항", "1-16"), ("PART 2", "결과보고서 및 점검결과 내역서", "17-18"), ("PART 3", "설비별 성능점검표 및 상세 검토", "19-")]
        return "<div class='title'>목차</div><table><tr><th>구분</th><th>내용</th><th>페이지</th></tr>" + "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a,b,c in rows) + "</table>"

    @staticmethod
    def _topic(description):
        return f"<div class='title'>기계설비 성능점검 일반사항</div><div class='box'><p>{_safe(description)}</p></div><div class='subtitle'>점검 기록 원칙</div><p>확인한 방법과 근거를 기록하고, 확인불가·해당없음·미점검을 최종판정과 구분하여 관리합니다.</p>"

    @staticmethod
    def _result_form(view):
        s = view.site
        return f"<div class='title'>기계설비 성능점검 결과보고서</div><table><tr><th>건축물명</th><td>{_safe(s.site_name)}</td><th>용도</th><td>{_safe(s.building_use)}</td></tr><tr><th>주소</th><td colspan='3'>{_safe(s.address)}</td></tr><tr><th>관리주체</th><td>{_safe(s.management_entity)}</td><th>연면적</th><td>{_safe(s.total_floor_area)}</td></tr><tr><th>점검기간</th><td>{_safe(s.inspection_period)}</td><th>작성일</th><td>{_safe(s.report_date)}</td></tr></table>"

    @staticmethod
    def _result_details(view):
        rows = "".join(f"<tr><td>{_safe(row.equipment_type)}</td><td>{_safe(row.management_no)}</td><td>{_safe(row.judgment_summary)}</td><td>{_safe(row.action_note)}</td></tr>" for row in view.result_rows)
        return "<div class='title'>점검결과 내역서</div><table class='result'><tr><th>설비종류</th><th>관리번호</th><th>점검결과</th><th>조치필요사항</th></tr>" + rows + "</table>"

    @staticmethod
    def _inspection_table(target, items, include_equipment):
        equipment = ""
        if include_equipment:
            equipment = f"<table class='equipment'><tr><td><b>설비종류</b> {_safe(target.equipment_type)}</td><td><b>관리번호</b> {_safe(target.management_no)}</td></tr><tr><td><b>설치위치</b> {_safe(target.location)}</td><td><b>주요사양</b> {_safe(target.specification)}</td></tr></table>"
            if target.overview_photo:
                equipment += f"<div><img class='photo' src='{_image_source(target.overview_photo.file_path)}'><div class='muted'>{_safe(target.overview_photo.caption)}</div></div>"
        rows = "".join(f"<tr><td>{_safe(i.item_no)}</td><td>{_safe(i.item_name)}</td><td>{_safe(i.inspection_method)}</td><td>{_safe(i.inspection_criteria)}</td><td>{_safe(i.reference_value)}</td><td>{_safe(i.measured_value)}</td><td>{_safe(i.judgment)}</td><td>{_safe(i.technical_note)}</td></tr>" for i in items)
        return equipment + "<table class='inspection'><tr><th>번호</th><th>점검내용</th><th>점검방법</th><th>점검기준</th><th>설계·정격값</th><th>측정·확인값</th><th>판정</th><th>기술적소견</th></tr>" + rows + "</table>"

    @staticmethod
    def _detail_items(items: list[ProductionInspectionItemView]):
        blocks = []
        for item in items:
            photos = "".join(f"<div><img class='photo' src='{_image_source(photo.file_path)}'><div class='muted'>{_safe(photo.caption)}</div></div>" for photo in item.photos)
            if not photos:
                photos = "<div class='muted'>등록된 항목 사진 없음</div>"
            blocks.append(f"<div class='detail'><div class='subtitle'>{_safe(item.item_no)}. {_safe(item.item_name)}</div><table class='detail-grid'><tr><td><p><b>점검방법</b> {_safe(item.inspection_method)}</p><p><b>점검기준</b> {_safe(item.inspection_criteria)}</p><p><b>설계·정격값</b> {_safe(item.reference_value)}</p><p><b>측정·확인값</b> {_safe(item.measured_value)}</p><p><b>판정</b> {_safe(item.judgment)}</p><p><b>기술적소견</b> {_safe(item.technical_note)}</p></td><td>{photos}</td></tr></table></div>")
        return "".join(blocks)

    @staticmethod
    def _empty_section(status: str) -> str:
        return f"<div class='box'><p><b>{_safe(status or '자료없음')}</b></p><p>저장된 검토자료가 없습니다.</p></div>"

    @classmethod
    def _system_summary(cls, view, start, stop):
        rows = view.system_review.summary_rows[start:stop]
        if not rows:
            return cls._empty_section(view.system_review.status)
        body = "".join(
            f"<tr><td>{_safe(row.review_item)}</td><td>{_safe(row.detail)}</td><td>{_safe(row.standard)}</td><td>{_safe(row.result)}</td></tr>"
            for row in rows
        )
        return "<div class='title'>시스템검토 요약</div><table class='system-summary'><tr><th>점검항목</th><th>세부 검토사항</th><th>검토기준</th><th>결과요약</th></tr>" + body + "</table>"

    @classmethod
    def _document_review(cls, view, start, stop):
        rows = view.system_review.document_rows[start:stop]
        if not rows:
            return cls._empty_section("자료없음")
        body = "".join(
            f"<tr><td>{_safe(row.document_name)}</td><td>{_safe(row.status)}</td><td>{_safe(row.engineer_note)}</td><td>{_safe(row.remark)}</td></tr>"
            for row in rows
        )
        return "<div class='title'>자료보유 및 확인사항</div><table class='document-review'><tr><th>구비서류</th><th>보유상태</th><th>책임기술자 소견</th><th>비고</th></tr>" + body + "</table>"

    @classmethod
    def _operation_review(cls, view, start, stop):
        rows = view.system_review.operation_rows[start:stop]
        if not rows:
            return cls._empty_section("자료없음")
        body = "".join(
            f"<tr><td>{_safe(row.review_type)}</td><td>{_safe(row.category)}</td><td>{_safe(row.equipment_name)}</td><td>{_safe(row.result)}</td><td>{_safe(row.basis)}</td><td>{_safe(row.remark)}</td></tr>"
            for row in rows
        )
        return "<div class='title'>작동상태 및 운전검토</div><table class='operation-review'><tr><th>검토구분</th><th>구분</th><th>대상설비</th><th>결과</th><th>비교근거</th><th>비고</th></tr>" + body + "</table>"

    @classmethod
    def _aging_review(cls, view, start, stop):
        rows = view.aging.rows[start:stop]
        if not rows:
            return cls._empty_section(view.aging.status)
        body = "".join(
            f"<tr><td>{_safe(row.equipment_type)}</td><td>{_safe(row.management_no)}</td><td>{_safe(row.installation_year)}</td><td>{_safe(row.reference_lifespan)}</td><td>{_safe(row.elapsed_years)}</td><td>{_safe(row.aging_status)}</td><td>{_safe(row.note)}</td></tr>"
            for row in rows
        )
        opinion = ""
        if stop == len(view.aging.rows):
            opinion = f"<div class='box'><p><b>적용근거</b> {_safe(view.aging.reference_source)}</p><p><b>종합의견</b> {_safe(view.aging.overall_opinion or '확인필요')}</p></div>"
        return "<div class='title'>노후도 분석</div><table class='aging-review'><tr><th>대상설비</th><th>관리번호</th><th>설치연도</th><th>참고 내용연수</th><th>사용연수</th><th>상태</th><th>비고</th></tr>" + body + "</table>" + opinion

    @classmethod
    def _improvement_review(cls, view, start, stop):
        rows = view.improvements.rows[start:stop]
        if not rows:
            return cls._empty_section(view.improvements.status)
        body = "".join(
            f"<tr><td>{_safe(row.section)}</td><td>{_safe(row.target_label)}</td><td>{_safe(row.issue)}</td><td>{_safe(row.action)}</td><td>{_safe(row.schedule)}</td><td>{_safe(row.status)}</td></tr>"
            for row in rows
        )
        return "<div class='title'>성능개선계획</div><table class='improvement-review'><tr><th>구분</th><th>대상설비</th><th>검토사항</th><th>개선내용</th><th>일정</th><th>상태</th></tr>" + body + "</table>"
