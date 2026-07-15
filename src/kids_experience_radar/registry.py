from __future__ import annotations

import os
from pathlib import Path

from .sources.base import Source
from .sources.configured_html import load_html_sources
from .sources.culture_portal import CulturePortalSource
from .sources.education_office import builtin_education_office_sources
from .sources.forest import ForestEducationSource
from .sources.ggc_events import GgcGyeonggiCultureSource
from .sources.goyang_children_museum import GoyangChildrenMuseumCityNewsSource
from .sources.gyeonggi_library import GyeonggiLibraryProgramSource
from .sources.gyeonggi_jang import GyeonggiJangProgramSource
from .sources.ggcf_affiliates import GgcfAffiliateProgramSource
from .sources.gyeongbuk_education import GyeongbukEducationExperienceSource
from .sources.hmoka import HmokaProgramSource
from .sources.hyundai_motorstudio import HyundaiMotorstudioKidsWorkshopSource
from .sources.jeonnam_art import JeonnamProvincialArtEducationSource
from .sources.kimchikan import KimchikanSource
from .sources.knps_trail_programs import KnpsTrailProgramSource
from .sources.kopis import KopisChildPerformanceSource
from .sources.koagi import KoagiEducationSource
from .sources.kywa import KywaYouthActivitySource
from .sources.kywa_camps import KywaCampSource
from .sources.leeum_hoam import LeeumHoamProgramSource
from .sources.modu_museum import ModuMuseumSource
from .sources.odcloud import builtin_odcloud_sources
from .sources.regional_reservations import builtin_regional_reservation_sources
from .sources.samsung_innovation import SamsungInnovationSource
from .sources.seoul import builtin_seoul_sources
from .sources.standard_data import (
    LifelongLearningCourseSource,
    NationalCultureFestivalSource,
)
from .sources.suwon_culture_foundation import SuwonCultureFoundationEducationSource
from .sources.suwon_ecology import SuwonEcologyProgramSource
from .sources.suwon_education import SuwonEducationSource
from .sources.suwon_library import SuwonLibraryProgramSource
from .sources.suwon_museums import builtin_suwon_museum_sources


def builtin_sources(*, html_config: str | Path | None = None) -> list[Source]:
    sources: list[Source] = []
    sources.extend(builtin_seoul_sources())
    sources.extend(
        [
            CulturePortalSource(service_type="C"),
            CulturePortalSource(service_type="B"),
            CulturePortalSource(service_type="A"),
            KopisChildPerformanceSource(),
            KywaYouthActivitySource(),
            ForestEducationSource(),
            LifelongLearningCourseSource(),
            NationalCultureFestivalSource(),
            GgcGyeonggiCultureSource(),
            GyeonggiJangProgramSource(),
            GgcfAffiliateProgramSource(),
            JeonnamProvincialArtEducationSource(),
        ]
    )
    sources.extend(builtin_odcloud_sources())
    sources.extend(ModuMuseumSource.all_sources())
    sources.extend(KoagiEducationSource.all_sources())
    sources.extend(KnpsTrailProgramSource.all_sources())
    sources.extend(KywaCampSource.all_sources())
    sources.append(GyeongbukEducationExperienceSource())
    sources.extend(builtin_education_office_sources())
    sources.extend(builtin_regional_reservation_sources())
    sources.append(SuwonEducationSource())
    sources.append(SuwonCultureFoundationEducationSource())
    sources.append(SuwonEcologyProgramSource())
    sources.append(SuwonLibraryProgramSource())
    sources.append(GoyangChildrenMuseumCityNewsSource())
    sources.append(GyeonggiLibraryProgramSource())
    sources.extend(builtin_suwon_museum_sources())
    try:
        from .sources.tour_api import TourFestivalSource

        sources.append(TourFestivalSource())
    except ImportError:
        pass
    try:
        from .sources.eshare import EshareEducationSource

        sources.append(EshareEducationSource())
    except ImportError:
        pass
    sources.extend(
        [
            HyundaiMotorstudioKidsWorkshopSource(),
            SamsungInnovationSource(),
            KimchikanSource(),
            HmokaProgramSource(),
            LeeumHoamProgramSource(),
        ]
    )
    config_path = html_config or os.getenv("KIDS_RADAR_HTML_CONFIG")
    if config_path:
        sources.extend(load_html_sources(config_path))
    return sources


def source_map(*, html_config: str | Path | None = None) -> dict[str, Source]:
    return {source.info.source_id: source for source in builtin_sources(html_config=html_config)}
