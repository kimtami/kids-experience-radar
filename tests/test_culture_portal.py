from kids_experience_radar.sources.culture_portal import CulturePortalSource


XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>OK</resultMsg></header>
  <body>
    <totalCount>1</totalCount>
    <items>
      <item>
        <seq>42</seq><title>초등 과학 교육 체험</title>
        <startDate>20260801</startDate><endDate>20260802</endDate>
        <place>어린이박물관</place><area>서울</area>
        <gpsX>126.98</gpsX><gpsY>37.57</gpsY>
        <price>무료</price><target>초등학생</target>
        <url>https://example.org/42</url>
      </item>
    </items>
  </body>
</response>"""


def test_parses_and_maps_culture_portal_xml() -> None:
    rows, total = CulturePortalSource.parse_rows(XML)
    assert total == 1
    event = CulturePortalSource()._map_row(rows[0])
    assert event.external_id == "42"
    assert event.price_min == 0
    assert event.latitude == 37.57
    assert event.longitude == 126.98
    assert event.age_min == 7
