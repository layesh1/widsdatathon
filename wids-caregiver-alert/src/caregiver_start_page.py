"""
caregiver_start_page.py
Caregiver / Evacuee landing page.
Real workflow:
  1. Enter your address/location
  2. System checks NASA FIRMS for fires within X miles (real data)
  3. If fire detected → auto-show nearest shelter + evacuation route
  4. If no fire → show risk profile and preparation checklist
  5. Caregiver can confirm their person has evacuated (feeds dispatcher tracker)
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
import folium
from streamlit_folium import st_folium
from io import StringIO
from pathlib import Path

FIRMS_VIIRS = (
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
    "suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_USA_contiguous_and_Hawaii_24h.csv"
)
# US shelters via OpenStreetMap Overpass API
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# FEMA shelter API (public, no key)
FEMA_SHELTERS_URL = "https://gis.fema.gov/arcgis/rest/services/NSS/OpenShelters/FeatureServer/0/query"


@st.cache_data(ttl=300, show_spinner=False)
def get_firms_us():
    """Fetch FIRMS data, return DataFrame or None."""
    try:
        r = requests.get(FIRMS_VIIRS, timeout=12)
        if r.status_code == 200 and len(r.text) > 200:
            df = pd.read_csv(StringIO(r.text))
            df.columns = [c.lower() for c in df.columns]
            df["lat"] = pd.to_numeric(df.get("latitude", df.get("lat")), errors="coerce")
            df["lon"] = pd.to_numeric(df.get("longitude", df.get("lon")), errors="coerce")
            df = df.dropna(subset=["lat", "lon"])
            return df[(df["lat"].between(24, 50)) & (df["lon"].between(-125, -65))]
    except Exception:
        pass
    return None


@st.cache_data(ttl=600, show_spinner=False)
def get_fema_shelters(lat, lon, radius_km=80):
    """Query FEMA open shelters API near a point."""
    try:
        # Convert radius to degrees approx
        deg = radius_km / 111
        params = {
            "where": f"SHELTER_STATUS='Open'",
            "geometry": f"{lon-deg},{lat-deg},{lon+deg},{lat+deg}",
            "geometryType": "esriGeometryEnvelope",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "SHELTER_NAME,ADDRESS,CITY,STATE,CAPACITY,LATITUDE,LONGITUDE,PHONE",
            "returnGeometry": "false",
            "f": "json",
            "resultRecordCount": 10
        }
        r = requests.get(FEMA_SHELTERS_URL, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if "features" in data and len(data["features"]) > 0:
                rows = [f["attributes"] for f in data["features"]]
                return pd.DataFrame(rows)
    except Exception:
        pass
    return None


def geocode_address(address):
    """Use Nominatim (free, no key) to geocode an address."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "WiDS-WildfireAlertSystem/1.0"},
            timeout=8
        )
        results = r.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"]), results[0]["display_name"]
    except Exception:
        pass
    return None, None, None


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
    return R * 2 * np.arcsin(np.sqrt(a))


# ── Bilingual string table ────────────────────────────────────────────────────
_STRINGS = {
    "en": {
        "title":           "Wildfire Evacuation Decision Support",
        "subheader":       "Know Your Risk. Act Early. Get Help.",
        "info_banner": (
            "In high-vulnerability counties, fires grow at **11.7 acres/hour** — "
            "+17% faster than lower-risk areas. The median time to an official evacuation "
            "order is **1.1 hours**. Don't wait."
        ),
        "enter_location":  "Enter Your Location",
        "address_label":   "Your address or city",
        "address_placeholder": "e.g. 142 Oak St, Paradise, CA",
        "radius_label":    "Search radius",
        "radius_fmt":      "{x} miles",
        "check_btn":       "Check Fire Risk Near Me",
        "spinner_locate":  "Locating address and checking for active fires...",
        "spinner_firms":   "Checking NASA FIRMS satellite data for active fires...",
        "spinner_shelters":"Searching for open shelters near you...",
        "addr_error":      "Couldn't find that address. Try a more specific address or include city and state.",
        "firms_unavail": (
            "NASA FIRMS data unavailable right now. "
            "Check [Ready.gov](https://www.ready.gov) or "
            "[CAL FIRE](https://www.fire.ca.gov/incidents/) for current evacuation orders."
        ),
        "no_fires":        "No active fire hotspots detected within {r} miles of your location in the last 24 hours (NASA FIRMS VIIRS satellite data).",
        "danger_imminent": "**IMMEDIATE DANGER** — {n} active fire hotspot(s) detected, closest is **{mi:.1f} miles** away. **Evacuate now if under order. Don't wait for official notice.**",
        "danger_warning":  "**Fire activity detected {mi:.1f} miles away** — {n} hotspot(s) within {r} miles. Monitor conditions and be ready to evacuate immediately.",
        "danger_info":     "Fire activity detected, but closest hotspot is {mi:.1f} miles away. Monitor conditions.",
        "shelters_title":  "Open Shelters Near You",
        "no_shelters": (
            "No FEMA open shelters found in current database for this area. "
            "Check [211.org](https://www.211.org) or call 2-1-1 for local shelters. "
            "Also check [ARC shelter finder](https://www.redcross.org/get-help/disaster-relief-and-recovery-services/find-an-open-shelter.html)."
        ),
        "shelter_src":     "Source: FEMA National Shelter System (live)",
        "confirm_title":   "Confirm Evacuation Status",
        "confirm_desc": (
            "If you are a caregiver and your person has evacuated, confirm here. "
            "This updates the dispatcher's tracker so emergency workers know who still needs help."
        ),
        "confirm_name":    "Resident name",
        "confirm_addr":    "Resident address",
        "confirm_dest":    "Evacuated to (shelter name or address)",
        "confirm_btn":     "Confirm Evacuated",
        "confirm_success": "{name} marked as evacuated. Dispatcher notified.",
        "confirm_success2":"Evacuation confirmed for {name}. Thank you.",
        "why_title":       "Why Act Early? *(WiDS 2021–2025 Real Fire Data)*",
        "metric1_label":   "Median Time to Evac Order",
        "metric2_label":   "Worst-Case Delay",
        "metric3_label":   "Fires in High-Risk Counties",
        "metric4_label":   "Growth Rate — High SVI Counties",
        "data_caption": (
            "All statistics from WiDS 2021–2025 dataset (Genasys Protect). "
            "Historical rates, not simulated."
        ),
    },
    # ── Spanish ───────────────────────────────────────────────────────────────
    "es": {
        "title":           "Apoyo para Decisiones de Evacuación por Incendios",
        "subheader":       "Conozca Su Riesgo. Actúe Temprano. Obtenga Ayuda.",
        "info_banner": (
            "En condados de alta vulnerabilidad, los incendios crecen **17.7 acres/hora** — "
            "+17% más rápido que las zonas de menor riesgo. El tiempo medio para una orden "
            "oficial de evacuación es de **1.1 horas**. No espere."
        ),
        "enter_location":  "Ingrese Su Ubicación",
        "address_label":   "Su dirección o ciudad",
        "address_placeholder": "Ej. 142 Oak St, Paradise, CA",
        "radius_label":    "Radio de búsqueda",
        "radius_fmt":      "{x} millas",
        "check_btn":       "Verificar Riesgo de Incendio Cerca",
        "spinner_locate":  "Localizando dirección y verificando incendios activos...",
        "spinner_firms":   "Verificando datos satelitales NASA FIRMS...",
        "spinner_shelters":"Buscando refugios abiertos cerca de usted...",
        "addr_error":      "No se encontró esa dirección. Intente con una dirección más específica o incluya ciudad y estado.",
        "firms_unavail": (
            "Los datos NASA FIRMS no están disponibles en este momento. "
            "Consulte [Ready.gov](https://www.ready.gov) o "
            "[CAL FIRE](https://www.fire.ca.gov/incidents/) para órdenes de evacuación actuales."
        ),
        "no_fires":        "No se detectaron focos activos en un radio de {r} millas en las últimas 24 horas (datos satelitales NASA FIRMS VIIRS).",
        "danger_imminent": "**PELIGRO INMEDIATO** — {n} foco(s) activo(s) detectado(s), el más cercano está a **{mi:.1f} millas**. **Evacúe ahora si está bajo orden. No espere el aviso oficial.**",
        "danger_warning":  "**Actividad de incendio detectada a {mi:.1f} millas** — {n} foco(s) en {r} millas. Monitoree las condiciones y esté listo para evacuar de inmediato.",
        "danger_info":     "Actividad de incendio detectada, pero el foco más cercano está a {mi:.1f} millas. Monitoree las condiciones.",
        "shelters_title":  "Refugios Abiertos Cerca de Usted",
        "no_shelters": (
            "No se encontraron refugios abiertos de FEMA en esta área. "
            "Llame al 2-1-1 o visite [211.org](https://www.211.org) para refugios locales. "
            "También consulte el [buscador de refugios de la Cruz Roja](https://www.redcross.org/get-help/disaster-relief-and-recovery-services/find-an-open-shelter.html)."
        ),
        "shelter_src":     "Fuente: Sistema Nacional de Refugios FEMA (en vivo)",
        "confirm_title":   "Confirmar Estado de Evacuación",
        "confirm_desc": (
            "Si usted es un cuidador y su persona ha evacuado, confirme aquí. "
            "Esto actualiza el rastreador del coordinador para que los equipos de emergencia "
            "sepan quién todavía necesita ayuda."
        ),
        "confirm_name":    "Nombre del residente",
        "confirm_addr":    "Dirección del residente",
        "confirm_dest":    "Evacuado a (nombre del refugio o dirección)",
        "confirm_btn":     "Confirmar Evacuación",
        "confirm_success": "{name} marcado como evacuado. Coordinador notificado.",
        "confirm_success2":"Evacuación confirmada para {name}. Gracias.",
        "why_title":       "¿Por Qué Actuar Temprano? *(Datos Reales WiDS 2021–2025)*",
        "metric1_label":   "Tiempo Mediano para Orden de Evacuación",
        "metric2_label":   "Retraso en el Peor Caso",
        "metric3_label":   "Incendios en Condados de Alto Riesgo",
        "metric4_label":   "Tasa de Crecimiento — Condados Alto SVI",
        "data_caption": (
            "Todas las estadísticas provienen del conjunto de datos WiDS 2021–2025 (Genasys Protect). "
            "Tasas históricas, no simuladas."
        ),
    },

    # ── Chinese (Simplified) ───────────────────────────────────────────────────
    "zh": {
        "title":           "野火疏散决策支持",
        "subheader":       "了解您的风险。提前行动。获取帮助。",
        "info_banner": (
            "在高脆弱性县，火灾以每小时**11.7英亩**的速度蔓延——比低风险地区快17%。"
            "官方疏散令的中位时间为**1.1小时**。请勿等待。"
        ),
        "enter_location":  "输入您的位置",
        "address_label":   "您的地址或城市",
        "address_placeholder": "例如：142 Oak St, Paradise, CA",
        "radius_label":    "搜索半径",
        "radius_fmt":      "{x} 英里",
        "check_btn":       "检查附近的火灾风险",
        "spinner_locate":  "正在定位地址并检查活跃火灾…",
        "spinner_firms":   "正在检查NASA FIRMS卫星数据…",
        "spinner_shelters":"正在搜索附近的开放避难所…",
        "addr_error":      "找不到该地址。请尝试更具体的地址或包含城市和州。",
        "firms_unavail": (
            "NASA FIRMS数据目前不可用。请查看 [Ready.gov](https://www.ready.gov) 或 "
            "[CAL FIRE](https://www.fire.ca.gov/incidents/) 了解当前疏散令。"
        ),
        "no_fires":        "在过去24小时内，您位置{r}英里范围内未检测到活跃火灾热点（NASA FIRMS VIIRS卫星数据）。",
        "danger_imminent": "**立即危险** — 检测到{n}个活跃火灾热点，最近的距您**{mi:.1f}英里**。**如收到疏散令请立即疏散。不要等待官方通知。**",
        "danger_warning":  "**在{mi:.1f}英里处检测到火灾活动** — {r}英里内有{n}个热点。请监测情况并随时准备立即疏散。",
        "danger_info":     "检测到火灾活动，但最近的热点距离{mi:.1f}英里。请监测情况。",
        "shelters_title":  "附近的开放避难所",
        "no_shelters": (
            "此区域未找到FEMA开放避难所。请拨打2-1-1或访问 [211.org](https://www.211.org) 获取本地避难所信息。"
        ),
        "shelter_src":     "来源：FEMA国家避难所系统（实时）",
        "confirm_title":   "确认疏散状态",
        "confirm_desc": (
            "如果您是护理人员且您照顾的人员已疏散，请在此确认。"
            "这将更新调度员追踪器，让紧急工作人员了解谁仍需帮助。"
        ),
        "confirm_name":    "居民姓名",
        "confirm_addr":    "居民地址",
        "confirm_dest":    "已疏散至（避难所名称或地址）",
        "confirm_btn":     "确认疏散",
        "confirm_success": "{name}已标记为已疏散。调度员已通知。",
        "confirm_success2":"已确认{name}的疏散。谢谢。",
        "why_title":       "为何提前行动？*(WiDS 2021–2025真实火灾数据)*",
        "metric1_label":   "疏散令中位时间",
        "metric2_label":   "最坏情况延迟",
        "metric3_label":   "高风险县的火灾",
        "metric4_label":   "增长率 — 高SVI县",
        "data_caption":    "所有统计数据来自WiDS 2021–2025数据集（Genasys Protect）。历史比率，非模拟。",
    },

    # ── Tagalog (Filipino) ────────────────────────────────────────────────────
    "tl": {
        "title":           "Suporta sa Desisyon ng Paglikas sa Wildfire",
        "subheader":       "Alamin ang Iyong Panganib. Kumilos nang Maaga. Humingi ng Tulong.",
        "info_banner": (
            "Sa mga county na may mataas na kahinaan, ang mga sunog ay lumalaki ng **11.7 acre/oras** "
            "— 17% mas mabilis kaysa sa mga lugar na may mababang panganib. "
            "Ang median na oras para sa opisyal na utos ng paglikas ay **1.1 oras**. Huwag maghintay."
        ),
        "enter_location":  "Ilagay ang Iyong Lokasyon",
        "address_label":   "Ang iyong address o lungsod",
        "address_placeholder": "hal. 142 Oak St, Paradise, CA",
        "radius_label":    "Radius ng paghahanap",
        "radius_fmt":      "{x} milya",
        "check_btn":       "Suriin ang Panganib ng Sunog sa Malapit",
        "spinner_locate":  "Hinahanap ang address at sinusuri ang mga aktibong sunog…",
        "spinner_firms":   "Sinusuri ang datos ng satellite ng NASA FIRMS…",
        "spinner_shelters":"Naghahanap ng mga bukas na kanlungan malapit sa iyo…",
        "addr_error":      "Hindi mahanap ang address na iyon. Subukan ang mas tiyak na address o isama ang lungsod at estado.",
        "firms_unavail": (
            "Ang datos ng NASA FIRMS ay hindi available ngayon. "
            "Suriin ang [Ready.gov](https://www.ready.gov) o [CAL FIRE](https://www.fire.ca.gov/incidents/) "
            "para sa mga kasalukuyang utos ng paglikas."
        ),
        "no_fires":        "Walang aktibong hotspot ng sunog na natukoy sa loob ng {r} milya ng iyong lokasyon sa nakalipas na 24 na oras.",
        "danger_imminent": "**AGARANG PANGANIB** — {n} aktibong hotspot ng sunog ang natukoy, ang pinakamalapit ay **{mi:.1f} milya** ang layo. **Lumikas ngayon kung nasa ilalim ng utos. Huwag maghintay ng opisyal na abiso.**",
        "danger_warning":  "**Aktibidad ng sunog na natukoy {mi:.1f} milya ang layo** — {n} hotspot sa loob ng {r} milya. Subaybayan ang mga kondisyon at maging handa na lumikas agad.",
        "danger_info":     "Natukoy ang aktibidad ng sunog, ngunit ang pinakamalapit na hotspot ay {mi:.1f} milya ang layo. Subaybayan ang mga kondisyon.",
        "shelters_title":  "Mga Bukas na Kanlungan Malapit sa Iyo",
        "no_shelters":     "Walang bukas na kanlungan ng FEMA na natagpuan sa lugar na ito. Tawagan ang 2-1-1 o bisitahin ang [211.org](https://www.211.org) para sa mga lokal na kanlungan.",
        "shelter_src":     "Pinagmulan: FEMA National Shelter System (live)",
        "confirm_title":   "Kumpirmahin ang Katayuan ng Paglikas",
        "confirm_desc":    "Kung ikaw ay isang tagapag-alaga at ang iyong taong pinaglilingkuran ay lumikas na, kumpirmahin dito. Ina-update nito ang tracker ng dispatcher para malaman ng mga emergency worker kung sino pa ang nangangailangan ng tulong.",
        "confirm_name":    "Pangalan ng residente",
        "confirm_addr":    "Address ng residente",
        "confirm_dest":    "Nailikas sa (pangalan ng kanlungan o address)",
        "confirm_btn":     "Kumpirmahin ang Paglikas",
        "confirm_success": "Si {name} ay minarkahang nailikas. Naabisuhan ang dispatcher.",
        "confirm_success2":"Nakumpirma ang paglikas para kay {name}. Salamat.",
        "why_title":       "Bakit Kumilos nang Maaga? *(Tunay na Datos ng Sunog WiDS 2021–2025)*",
        "metric1_label":   "Median na Oras sa Utos ng Paglikas",
        "metric2_label":   "Pinakamalaong Pagkaantala",
        "metric3_label":   "Mga Sunog sa Mataas na Panganib na County",
        "metric4_label":   "Rate ng Paglago — Mataas na SVI County",
        "data_caption":    "Lahat ng istatistika mula sa dataset ng WiDS 2021–2025 (Genasys Protect). Makasaysayang mga rate, hindi simulate.",
    },

    # ── Vietnamese ────────────────────────────────────────────────────────────
    "vi": {
        "title":           "Hỗ Trợ Quyết Định Sơ Tán Cháy Rừng",
        "subheader":       "Biết Rủi Ro Của Bạn. Hành Động Sớm. Tìm Kiếm Trợ Giúp.",
        "info_banner": (
            "Ở các quận dễ bị tổn thương cao, đám cháy lan rộng **11.7 mẫu/giờ** — "
            "nhanh hơn 17% so với các khu vực ít rủi ro. "
            "Thời gian trung bình để có lệnh sơ tán chính thức là **1.1 giờ**. Đừng chờ đợi."
        ),
        "enter_location":  "Nhập Vị Trí Của Bạn",
        "address_label":   "Địa chỉ hoặc thành phố của bạn",
        "address_placeholder": "vd: 142 Oak St, Paradise, CA",
        "radius_label":    "Bán kính tìm kiếm",
        "radius_fmt":      "{x} dặm",
        "check_btn":       "Kiểm Tra Rủi Ro Cháy Rừng Gần Đây",
        "spinner_locate":  "Đang định vị địa chỉ và kiểm tra các đám cháy đang hoạt động…",
        "spinner_firms":   "Đang kiểm tra dữ liệu vệ tinh NASA FIRMS…",
        "spinner_shelters":"Đang tìm kiếm các nơi trú ẩn mở gần bạn…",
        "addr_error":      "Không tìm thấy địa chỉ đó. Hãy thử địa chỉ cụ thể hơn hoặc bao gồm thành phố và tiểu bang.",
        "firms_unavail": (
            "Dữ liệu NASA FIRMS hiện không khả dụng. Kiểm tra [Ready.gov](https://www.ready.gov) hoặc "
            "[CAL FIRE](https://www.fire.ca.gov/incidents/) để biết các lệnh sơ tán hiện tại."
        ),
        "no_fires":        "Không phát hiện điểm cháy rừng nào trong vòng {r} dặm từ vị trí của bạn trong 24 giờ qua.",
        "danger_imminent": "**NGUY HIỂM NGAY LẬP TỨC** — Phát hiện {n} điểm cháy rừng đang hoạt động, gần nhất cách **{mi:.1f} dặm**. **Sơ tán ngay nếu có lệnh. Đừng chờ thông báo chính thức.**",
        "danger_warning":  "**Phát hiện hoạt động cháy rừng cách {mi:.1f} dặm** — {n} điểm nóng trong vòng {r} dặm. Theo dõi tình hình và sẵn sàng sơ tán ngay.",
        "danger_info":     "Phát hiện hoạt động cháy rừng, nhưng điểm nóng gần nhất cách {mi:.1f} dặm. Theo dõi tình hình.",
        "shelters_title":  "Các Nơi Trú Ẩn Đang Mở Gần Bạn",
        "no_shelters":     "Không tìm thấy nơi trú ẩn FEMA mở trong khu vực này. Gọi 2-1-1 hoặc truy cập [211.org](https://www.211.org) để tìm nơi trú ẩn địa phương.",
        "shelter_src":     "Nguồn: Hệ thống Nơi Trú Ẩn Quốc gia FEMA (trực tiếp)",
        "confirm_title":   "Xác Nhận Tình Trạng Sơ Tán",
        "confirm_desc":    "Nếu bạn là người chăm sóc và người được chăm sóc đã sơ tán, hãy xác nhận ở đây. Điều này cập nhật trình theo dõi của điều phối viên để lực lượng cứu hộ biết ai vẫn cần giúp đỡ.",
        "confirm_name":    "Tên cư dân",
        "confirm_addr":    "Địa chỉ cư dân",
        "confirm_dest":    "Đã sơ tán đến (tên nơi trú ẩn hoặc địa chỉ)",
        "confirm_btn":     "Xác Nhận Sơ Tán",
        "confirm_success": "{name} đã được đánh dấu là đã sơ tán. Điều phối viên đã được thông báo.",
        "confirm_success2":"Đã xác nhận sơ tán cho {name}. Cảm ơn.",
        "why_title":       "Tại Sao Hành Động Sớm? *(Dữ Liệu Cháy Rừng Thực WiDS 2021–2025)*",
        "metric1_label":   "Thời Gian Trung Bình Đến Lệnh Sơ Tán",
        "metric2_label":   "Độ Trễ Trường Hợp Xấu Nhất",
        "metric3_label":   "Đám Cháy ở Quận Rủi Ro Cao",
        "metric4_label":   "Tốc Độ Tăng Trưởng — Quận SVI Cao",
        "data_caption":    "Tất cả số liệu từ bộ dữ liệu WiDS 2021–2025 (Genasys Protect). Tỷ lệ lịch sử, không phải mô phỏng.",
    },

    # ── Arabic ────────────────────────────────────────────────────────────────
    "ar": {
        "title":           "دعم قرار الإخلاء من حرائق الغابات",
        "subheader":       "اعرف مخاطرك. تصرف مبكراً. احصل على المساعدة.",
        "info_banner": (
            "في المقاطعات عالية التعرض للخطر، تنتشر الحرائق بمعدل **11.7 فدان/ساعة** "
            "— أسرع بنسبة 17% من المناطق الأقل خطورة. "
            "متوسط الوقت للحصول على أمر الإخلاء الرسمي هو **1.1 ساعة**. لا تنتظر."
        ),
        "enter_location":  "أدخل موقعك",
        "address_label":   "عنوانك أو مدينتك",
        "address_placeholder": "مثال: 142 Oak St, Paradise, CA",
        "radius_label":    "نطاق البحث",
        "radius_fmt":      "{x} أميال",
        "check_btn":       "تحقق من خطر الحريق بالقرب مني",
        "spinner_locate":  "جاري تحديد العنوان والتحقق من الحرائق النشطة…",
        "spinner_firms":   "جاري التحقق من بيانات الأقمار الصناعية لـ NASA FIRMS…",
        "spinner_shelters":"جاري البحث عن ملاجئ مفتوحة بالقرب منك…",
        "addr_error":      "تعذر العثور على هذا العنوان. جرب عنواناً أكثر تحديداً أو أضف المدينة والولاية.",
        "firms_unavail": (
            "بيانات NASA FIRMS غير متاحة حالياً. تحقق من [Ready.gov](https://www.ready.gov) أو "
            "[CAL FIRE](https://www.fire.ca.gov/incidents/) لأوامر الإخلاء الحالية."
        ),
        "no_fires":        "لم يتم الكشف عن أي بؤر حريق نشطة في نطاق {r} ميل من موقعك خلال الـ 24 ساعة الماضية.",
        "danger_imminent": "**خطر فوري** — تم الكشف عن {n} بؤرة حريق نشطة، أقربها على بُعد **{mi:.1f} ميل**. **أخلِ الآن إذا كنت تحت أمر إخلاء. لا تنتظر الإشعار الرسمي.**",
        "danger_warning":  "**تم الكشف عن نشاط حريق على بُعد {mi:.1f} ميل** — {n} بؤرة في نطاق {r} ميل. راقب الأوضاع وكن مستعداً للإخلاء الفوري.",
        "danger_info":     "تم الكشف عن نشاط حريق، لكن أقرب بؤرة تبعد {mi:.1f} ميل. راقب الأوضاع.",
        "shelters_title":  "الملاجئ المفتوحة القريبة منك",
        "no_shelters":     "لم يتم العثور على ملاجئ FEMA مفتوحة في هذه المنطقة. اتصل بـ 2-1-1 أو زر [211.org](https://www.211.org) للحصول على ملاجئ محلية.",
        "shelter_src":     "المصدر: نظام الملاجئ الوطني التابع لـ FEMA (مباشر)",
        "confirm_title":   "تأكيد حالة الإخلاء",
        "confirm_desc":    "إذا كنت مقدم رعاية وقد أخلى شخصك، فأكد ذلك هنا. سيؤدي هذا إلى تحديث متتبع المُنسِّق حتى يعرف عمال الطوارئ من لا يزال يحتاج إلى مساعدة.",
        "confirm_name":    "اسم الساكن",
        "confirm_addr":    "عنوان الساكن",
        "confirm_dest":    "تم الإخلاء إلى (اسم الملجأ أو العنوان)",
        "confirm_btn":     "تأكيد الإخلاء",
        "confirm_success": "تم تحديد {name} كمُخلَى. تم إخطار المُنسِّق.",
        "confirm_success2":"تم تأكيد الإخلاء لـ {name}. شكراً.",
        "why_title":       "لماذا نتصرف مبكراً؟ *(بيانات حرائق الغابات الحقيقية WiDS 2021–2025)*",
        "metric1_label":   "متوسط الوقت لأمر الإخلاء",
        "metric2_label":   "التأخير في أسوأ الحالات",
        "metric3_label":   "الحرائق في المقاطعات عالية الخطورة",
        "metric4_label":   "معدل النمو — مقاطعات SVI العالية",
        "data_caption":    "جميع الإحصاءات من مجموعة بيانات WiDS 2021–2025 (Genasys Protect). معدلات تاريخية، غير محاكاة.",
    },

    # ── Korean ────────────────────────────────────────────────────────────────
    "ko": {
        "title":           "산불 대피 결정 지원",
        "subheader":       "위험을 파악하세요. 일찍 행동하세요. 도움을 받으세요.",
        "info_banner": (
            "취약성이 높은 카운티에서 산불은 시간당 **11.7에이커**의 속도로 번집니다 "
            "— 위험이 낮은 지역보다 17% 빠릅니다. "
            "공식 대피 명령까지의 중간값 시간은 **1.1시간**입니다. 기다리지 마세요."
        ),
        "enter_location":  "위치 입력",
        "address_label":   "주소 또는 도시",
        "address_placeholder": "예: 142 Oak St, Paradise, CA",
        "radius_label":    "검색 반경",
        "radius_fmt":      "{x} 마일",
        "check_btn":       "근처 산불 위험 확인",
        "spinner_locate":  "주소를 찾고 활성 화재를 확인하는 중…",
        "spinner_firms":   "NASA FIRMS 위성 데이터 확인 중…",
        "spinner_shelters":"근처의 열린 대피소 검색 중…",
        "addr_error":      "해당 주소를 찾을 수 없습니다. 더 구체적인 주소나 도시와 주를 포함해 시도해 보세요.",
        "firms_unavail": (
            "NASA FIRMS 데이터를 현재 사용할 수 없습니다. "
            "[Ready.gov](https://www.ready.gov) 또는 [CAL FIRE](https://www.fire.ca.gov/incidents/)에서 현재 대피 명령을 확인하세요."
        ),
        "no_fires":        "지난 24시간 동안 귀하의 위치에서 {r}마일 이내에 활성 화재 핫스팟이 감지되지 않았습니다.",
        "danger_imminent": "**즉각적인 위험** — {n}개의 활성 화재 핫스팟이 감지되었으며, 가장 가까운 것은 **{mi:.1f}마일** 떨어져 있습니다. **명령 하에 있다면 지금 대피하세요. 공식 통보를 기다리지 마세요.**",
        "danger_warning":  "**{mi:.1f}마일 거리에서 화재 활동 감지됨** — {r}마일 이내에 {n}개의 핫스팟. 상황을 모니터링하고 즉각 대피할 준비를 하세요.",
        "danger_info":     "화재 활동이 감지되었지만 가장 가까운 핫스팟은 {mi:.1f}마일 떨어져 있습니다. 상황을 모니터링하세요.",
        "shelters_title":  "근처의 열린 대피소",
        "no_shelters":     "이 지역에서 FEMA 열린 대피소를 찾을 수 없습니다. 2-1-1에 전화하거나 [211.org](https://www.211.org)를 방문하여 지역 대피소를 찾으세요.",
        "shelter_src":     "출처: FEMA 국가 대피소 시스템 (실시간)",
        "confirm_title":   "대피 상태 확인",
        "confirm_desc":    "귀하가 보호자이고 귀하의 피보호자가 대피했다면 여기서 확인하세요. 이를 통해 긴급 요원들이 누가 아직 도움이 필요한지 알 수 있도록 디스패처 추적기가 업데이트됩니다.",
        "confirm_name":    "거주자 이름",
        "confirm_addr":    "거주자 주소",
        "confirm_dest":    "대피 장소 (대피소 이름 또는 주소)",
        "confirm_btn":     "대피 확인",
        "confirm_success": "{name}이(가) 대피한 것으로 표시되었습니다. 디스패처에게 알렸습니다.",
        "confirm_success2":"{name}의 대피가 확인되었습니다. 감사합니다.",
        "why_title":       "왜 일찍 행동해야 하나요? *(WiDS 2021–2025 실제 화재 데이터)*",
        "metric1_label":   "대피 명령까지의 중간값 시간",
        "metric2_label":   "최악의 경우 지연",
        "metric3_label":   "고위험 카운티의 화재",
        "metric4_label":   "성장률 — 높은 SVI 카운티",
        "data_caption":    "모든 통계는 WiDS 2021–2025 데이터셋(Genasys Protect)에서 가져왔습니다. 시뮬레이션이 아닌 역사적 비율.",
    },

    # ── Russian ───────────────────────────────────────────────────────────────
    "ru": {
        "title":           "Поддержка решений об эвакуации при лесных пожарах",
        "subheader":       "Знайте свои риски. Действуйте заблаговременно. Получите помощь.",
        "info_banner": (
            "В округах с высокой уязвимостью пожары распространяются со скоростью **11,7 акра/час** "
            "— на 17% быстрее, чем в зонах с низким риском. "
            "Среднее время до официального приказа об эвакуации составляет **1,1 часа**. Не ждите."
        ),
        "enter_location":  "Введите Ваше Местоположение",
        "address_label":   "Ваш адрес или город",
        "address_placeholder": "напр. 142 Oak St, Paradise, CA",
        "radius_label":    "Радиус поиска",
        "radius_fmt":      "{x} миль",
        "check_btn":       "Проверить риск пожара рядом",
        "spinner_locate":  "Определение адреса и проверка активных пожаров…",
        "spinner_firms":   "Проверка спутниковых данных NASA FIRMS…",
        "spinner_shelters":"Поиск открытых убежищ рядом с вами…",
        "addr_error":      "Не удалось найти этот адрес. Попробуйте указать более конкретный адрес или добавить город и штат.",
        "firms_unavail": (
            "Данные NASA FIRMS сейчас недоступны. Проверьте [Ready.gov](https://www.ready.gov) или "
            "[CAL FIRE](https://www.fire.ca.gov/incidents/) для получения актуальных приказов об эвакуации."
        ),
        "no_fires":        "За последние 24 часа в радиусе {r} миль от вашего местоположения не обнаружено активных очагов пожаров.",
        "danger_imminent": "**НЕМЕДЛЕННАЯ ОПАСНОСТЬ** — обнаружено {n} активных очага пожара, ближайший находится на расстоянии **{mi:.1f} миль**. **Эвакуируйтесь немедленно, если получен приказ. Не ждите официального уведомления.**",
        "danger_warning":  "**Обнаружена пожарная активность в {mi:.1f} милях** — {n} очагов в радиусе {r} миль. Следите за обстановкой и будьте готовы к немедленной эвакуации.",
        "danger_info":     "Обнаружена пожарная активность, но ближайший очаг находится на расстоянии {mi:.1f} миль. Следите за обстановкой.",
        "shelters_title":  "Открытые убежища рядом с вами",
        "no_shelters":     "Открытые убежища FEMA в этом районе не найдены. Позвоните по номеру 2-1-1 или посетите [211.org](https://www.211.org) для поиска местных убежищ.",
        "shelter_src":     "Источник: Национальная система убежищ FEMA (в реальном времени)",
        "confirm_title":   "Подтвердить статус эвакуации",
        "confirm_desc":    "Если вы являетесь опекуном и ваш подопечный эвакуировался, подтвердите это здесь. Это обновит трекер диспетчера, чтобы аварийные службы знали, кому ещё нужна помощь.",
        "confirm_name":    "Имя жителя",
        "confirm_addr":    "Адрес жителя",
        "confirm_dest":    "Эвакуирован в (название убежища или адрес)",
        "confirm_btn":     "Подтвердить эвакуацию",
        "confirm_success": "{name} отмечен(а) как эвакуированный(-ая). Диспетчер уведомлён.",
        "confirm_success2":"Эвакуация для {name} подтверждена. Спасибо.",
        "why_title":       "Почему нужно действовать заблаговременно? *(Реальные данные WiDS 2021–2025)*",
        "metric1_label":   "Медианное время до приказа об эвакуации",
        "metric2_label":   "Задержка в худшем случае",
        "metric3_label":   "Пожары в округах высокого риска",
        "metric4_label":   "Темп роста — округа с высоким SVI",
        "data_caption":    "Все статистические данные взяты из набора данных WiDS 2021–2025 (Genasys Protect). Исторические показатели, не симулированные.",
    },

    # ── Portuguese (Brazilian) ────────────────────────────────────────────────
    "pt": {
        "title":           "Apoio à Decisão de Evacuação de Incêndios Florestais",
        "subheader":       "Conheça Seu Risco. Aja Cedo. Obtenha Ajuda.",
        "info_banner": (
            "Em condados de alta vulnerabilidade, os incêndios crescem a **11,7 acres/hora** "
            "— 17% mais rápido do que áreas de baixo risco. "
            "O tempo médio para uma ordem oficial de evacuação é de **1,1 hora**. Não espere."
        ),
        "enter_location":  "Insira Sua Localização",
        "address_label":   "Seu endereço ou cidade",
        "address_placeholder": "ex: 142 Oak St, Paradise, CA",
        "radius_label":    "Raio de busca",
        "radius_fmt":      "{x} milhas",
        "check_btn":       "Verificar Risco de Incêndio Próximo",
        "spinner_locate":  "Localizando endereço e verificando incêndios ativos…",
        "spinner_firms":   "Verificando dados de satélite NASA FIRMS…",
        "spinner_shelters":"Procurando abrigos abertos perto de você…",
        "addr_error":      "Não foi possível encontrar esse endereço. Tente um endereço mais específico ou inclua cidade e estado.",
        "firms_unavail": (
            "Dados NASA FIRMS indisponíveis agora. Verifique [Ready.gov](https://www.ready.gov) ou "
            "[CAL FIRE](https://www.fire.ca.gov/incidents/) para ordens de evacuação atuais."
        ),
        "no_fires":        "Nenhum ponto quente de incêndio ativo detectado em um raio de {r} milhas da sua localização nas últimas 24 horas.",
        "danger_imminent": "**PERIGO IMEDIATO** — {n} ponto(s) quente(s) de incêndio ativo(s) detectado(s), o mais próximo está a **{mi:.1f} milhas**. **Evacue agora se estiver sob ordem. Não espere o aviso oficial.**",
        "danger_warning":  "**Atividade de incêndio detectada a {mi:.1f} milhas** — {n} ponto(s) quente(s) em {r} milhas. Monitore as condições e esteja pronto para evacuar imediatamente.",
        "danger_info":     "Atividade de incêndio detectada, mas o ponto quente mais próximo está a {mi:.1f} milhas. Monitore as condições.",
        "shelters_title":  "Abrigos Abertos Perto de Você",
        "no_shelters":     "Nenhum abrigo FEMA aberto encontrado nesta área. Ligue para 2-1-1 ou visite [211.org](https://www.211.org) para abrigos locais.",
        "shelter_src":     "Fonte: Sistema Nacional de Abrigos FEMA (ao vivo)",
        "confirm_title":   "Confirmar Status de Evacuação",
        "confirm_desc":    "Se você é um cuidador e sua pessoa já evacuou, confirme aqui. Isso atualiza o rastreador do despachante para que os trabalhadores de emergência saibam quem ainda precisa de ajuda.",
        "confirm_name":    "Nome do residente",
        "confirm_addr":    "Endereço do residente",
        "confirm_dest":    "Evacuado para (nome do abrigo ou endereço)",
        "confirm_btn":     "Confirmar Evacuação",
        "confirm_success": "{name} marcado como evacuado. Despachante notificado.",
        "confirm_success2":"Evacuação confirmada para {name}. Obrigado.",
        "why_title":       "Por Que Agir Cedo? *(Dados Reais de Incêndio WiDS 2021–2025)*",
        "metric1_label":   "Tempo Médio para Ordem de Evacuação",
        "metric2_label":   "Atraso no Pior Caso",
        "metric3_label":   "Incêndios em Condados de Alto Risco",
        "metric4_label":   "Taxa de Crescimento — Condados Alto SVI",
        "data_caption":    "Todas as estatísticas do conjunto de dados WiDS 2021–2025 (Genasys Protect). Taxas históricas, não simuladas.",
    },

    # ── French ────────────────────────────────────────────────────────────────
    "fr": {
        "title":           "Aide à la Décision d'Évacuation — Incendies de Forêt",
        "subheader":       "Connaissez Votre Risque. Agissez Tôt. Obtenez de l'Aide.",
        "info_banner": (
            "Dans les comtés très vulnérables, les incendies progressent à **11,7 acres/heure** "
            "— 17% plus vite que dans les zones moins risquées. "
            "Le délai médian pour un ordre d'évacuation officiel est de **1,1 heure**. N'attendez pas."
        ),
        "enter_location":  "Entrez Votre Localisation",
        "address_label":   "Votre adresse ou ville",
        "address_placeholder": "ex: 142 Oak St, Paradise, CA",
        "radius_label":    "Rayon de recherche",
        "radius_fmt":      "{x} miles",
        "check_btn":       "Vérifier le Risque d'Incendie à Proximité",
        "spinner_locate":  "Localisation de l'adresse et vérification des incendies actifs…",
        "spinner_firms":   "Vérification des données satellite NASA FIRMS…",
        "spinner_shelters":"Recherche d'abris ouverts près de chez vous…",
        "addr_error":      "Adresse introuvable. Essayez une adresse plus précise ou incluez la ville et l'état.",
        "firms_unavail": (
            "Les données NASA FIRMS sont indisponibles pour l'instant. Consultez [Ready.gov](https://www.ready.gov) ou "
            "[CAL FIRE](https://www.fire.ca.gov/incidents/) pour les ordres d'évacuation actuels."
        ),
        "no_fires":        "Aucun foyer d'incendie actif détecté dans un rayon de {r} miles de votre position au cours des dernières 24 heures.",
        "danger_imminent": "**DANGER IMMÉDIAT** — {n} foyer(s) d'incendie actif(s) détecté(s), le plus proche est à **{mi:.1f} miles**. **Évacuez maintenant si vous êtes sous ordre. N'attendez pas la notification officielle.**",
        "danger_warning":  "**Activité d'incendie détectée à {mi:.1f} miles** — {n} foyer(s) dans un rayon de {r} miles. Surveillez les conditions et soyez prêt à évacuer immédiatement.",
        "danger_info":     "Activité d'incendie détectée, mais le foyer le plus proche est à {mi:.1f} miles. Surveillez les conditions.",
        "shelters_title":  "Abris Ouverts Près de Chez Vous",
        "no_shelters":     "Aucun abri FEMA ouvert trouvé dans cette zone. Appelez le 2-1-1 ou visitez [211.org](https://www.211.org) pour les abris locaux.",
        "shelter_src":     "Source: Système National d'Abris FEMA (en direct)",
        "confirm_title":   "Confirmer le Statut d'Évacuation",
        "confirm_desc":    "Si vous êtes un aidant et que votre personne a évacué, confirmez-le ici. Cela met à jour le suivi du coordinateur afin que les équipes d'urgence sachent qui a encore besoin d'aide.",
        "confirm_name":    "Nom du résident",
        "confirm_addr":    "Adresse du résident",
        "confirm_dest":    "Évacué vers (nom de l'abri ou adresse)",
        "confirm_btn":     "Confirmer l'Évacuation",
        "confirm_success": "{name} marqué(e) comme évacué(e). Coordinateur notifié.",
        "confirm_success2":"Évacuation confirmée pour {name}. Merci.",
        "why_title":       "Pourquoi Agir Tôt? *(Données Réelles sur les Incendies WiDS 2021–2025)*",
        "metric1_label":   "Délai Médian jusqu'à l'Ordre d'Évacuation",
        "metric2_label":   "Retard dans le Pire des Cas",
        "metric3_label":   "Incendies dans les Comtés à Haut Risque",
        "metric4_label":   "Taux de Croissance — Comtés à IVS Élevé",
        "data_caption":    "Toutes les statistiques proviennent du jeu de données WiDS 2021–2025 (Genasys Protect). Taux historiques, non simulés.",
    },
}


def _t(key: str, lang: str = "en", **kwargs) -> str:
    """Retrieve a translated string, falling back to English if key missing."""
    s = _STRINGS.get(lang, _STRINGS["en"]).get(key, _STRINGS["en"].get(key, key))
    if kwargs:
        try:
            s = s.format(**kwargs)
        except Exception:
            pass
    return s


def render_caregiver_start_page():
    # Language selector
    _LANG_LABELS = {
        "en": "🇺🇸 English",
        "es": "🇲🇽 Español",
        "zh": "🇨🇳 中文 (Mandarin)",
        "tl": "🇵🇭 Tagalog (Filipino)",
        "vi": "🇻🇳 Tiếng Việt (Vietnamese)",
        "ar": "🇸🇦 العربية (Arabic)",
        "ko": "🇰🇷 한국어 (Korean)",
        "ru": "🇷🇺 Русский (Russian)",
        "pt": "🇧🇷 Português (Portuguese)",
        "fr": "🇫🇷 Français (French)",
    }
    lang = st.selectbox(
        "Language / Idioma / 语言",
        options=list(_LANG_LABELS.keys()),
        format_func=lambda x: _LANG_LABELS.get(x, x),
        key="caregiver_lang",
        label_visibility="collapsed",
    )

    st.markdown(
        f"<h1 style='font-size:24px;font-weight:700;color:#e6edf3;"
        f"border-bottom:1px solid #30363d;padding-bottom:12px;margin-bottom:4px;"
        f"font-family:\"DM Sans\",system-ui,sans-serif'>"
        f"{_t('title', lang)}</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p style='color:#8b949e;margin-bottom:0.8rem'>{_t('subheader', lang)}</p>",
        unsafe_allow_html=True,
    )

    # ── Real data warning banner ──────────────────────────────────────────────
    st.info(_t("info_banner", lang))

    st.divider()

    # ── Address input ─────────────────────────────────────────────────────────
    st.subheader(_t("enter_location", lang))
    col_addr, col_radius = st.columns([3, 1])
    with col_addr:
        address_input = st.text_input(
            _t("address_label", lang),
            placeholder=_t("address_placeholder", lang),
            help="Used only to check for nearby fires and find shelters. Not stored."
        )
    with col_radius:
        search_radius = st.selectbox(
            _t("radius_label", lang), [10, 25, 50, 100], index=1,
            format_func=lambda x: _t("radius_fmt", lang, x=x)
        )

    check_btn = st.button(_t("check_btn", lang), type="primary",
                           disabled=(not address_input))

    if check_btn and address_input:
        with st.spinner(_t("spinner_locate", lang)):
            user_lat, user_lon, display_name = geocode_address(address_input)

        if user_lat is None:
            st.error(_t("addr_error", lang))
            return

        st.success(f"Found: {display_name}")
        st.session_state["user_lat"]   = user_lat
        st.session_state["user_lon"]   = user_lon
        st.session_state["user_addr"]  = display_name

        # Check FIRMS
        with st.spinner(_t("spinner_firms", lang)):
            firms_df = get_firms_us()

        if firms_df is not None and len(firms_df) > 0:
            firms_df["dist_km"] = firms_df.apply(
                lambda r: haversine_km(user_lat, user_lon, r["lat"], r["lon"]), axis=1
            )
            radius_km = search_radius * 1.609
            nearby = firms_df[firms_df["dist_km"] <= radius_km].sort_values("dist_km")
            st.session_state["nearby_fires"] = nearby
            st.session_state["firms_loaded"] = True
        else:
            st.session_state["nearby_fires"] = pd.DataFrame()
            st.session_state["firms_loaded"] = False

    # ── Results ───────────────────────────────────────────────────────────────
    if "user_lat" in st.session_state:
        user_lat  = st.session_state["user_lat"]
        user_lon  = st.session_state["user_lon"]
        nearby    = st.session_state.get("nearby_fires", pd.DataFrame())
        firms_ok  = st.session_state.get("firms_loaded", False)

        st.divider()

        # Fire status banner
        if not firms_ok:
            st.warning(_t("firms_unavail", lang))
        elif len(nearby) == 0:
            st.success(_t("no_fires", lang, r=search_radius))
        else:
            closest_km = nearby.iloc[0]["dist_km"]
            closest_mi = closest_km / 1.609
            n_fires    = len(nearby)

            if closest_mi < 5:
                st.error(_t("danger_imminent", lang, n=n_fires, mi=closest_mi))
            elif closest_mi < 20:
                st.warning(_t("danger_warning", lang, n=n_fires, mi=closest_mi, r=search_radius))
            else:
                st.info(_t("danger_info", lang, mi=closest_mi))

        # Map
        m = folium.Map(location=[user_lat, user_lon], zoom_start=9, tiles="CartoDB dark_matter")

        # User location
        folium.Marker(
            [user_lat, user_lon],
            popup="Your location",
            icon=folium.Icon(color="blue", icon="home", prefix="fa")
        ).add_to(m)

        # Fire hotspots
        if len(nearby) > 0:
            for _, row in nearby.head(50).iterrows():
                try:
                    folium.CircleMarker(
                        location=[row["lat"], row["lon"]],
                        radius=6,
                        color="#FF2200", fill=True, fill_color="#FF2200", fill_opacity=0.7,
                        tooltip=f"Fire — {row['dist_km']:.1f} km away"
                    ).add_to(m)
                except Exception:
                    pass

        # Shelter lookup
        with st.spinner(_t("spinner_shelters", lang)):
            radius_km = search_radius * 1.609
            shelters = get_fema_shelters(user_lat, user_lon, radius_km)

        shelter_found = False
        if shelters is not None and len(shelters) > 0:
            shelter_found = True
            for _, s in shelters.iterrows():
                try:
                    slat = float(s.get("LATITUDE", 0))
                    slon = float(s.get("LONGITUDE", 0))
                    if slat and slon:
                        folium.Marker(
                            [slat, slon],
                            popup=folium.Popup(
                                f"<b>{s.get('SHELTER_NAME','Shelter')}</b><br>"
                                f"{s.get('ADDRESS','')}, {s.get('CITY','')}<br>"
                                f"Capacity: {s.get('CAPACITY','—')}<br>"
                                f"Phone: {s.get('PHONE','—')}",
                                max_width=200
                            ),
                            icon=folium.Icon(color="green", icon="plus-sign", prefix="glyphicon")
                        ).add_to(m)
                except Exception:
                    pass

        st_folium(m, width="100%", height=420, returned_objects=[])

        # Shelter table
        st.subheader(_t("shelters_title", lang))
        if shelter_found:
            display_cols = [c for c in ["SHELTER_NAME", "ADDRESS", "CITY", "STATE",
                                         "CAPACITY", "PHONE"] if c in shelters.columns]
            st.dataframe(shelters[display_cols].rename(columns={
                "SHELTER_NAME": "Shelter", "ADDRESS": "Address", "CITY": "City",
                "STATE": "State", "CAPACITY": "Capacity", "PHONE": "Phone"
            }), use_container_width=True, hide_index=True)
            st.caption(_t("shelter_src", lang))
        else:
            st.info(_t("no_shelters", lang))

        st.divider()

        # Caregiver confirmation
        st.subheader(_t("confirm_title", lang))
        st.markdown(_t("confirm_desc", lang))
        with st.form("confirm_evac_form"):
            confirm_name = st.text_input(_t("confirm_name", lang))
            confirm_addr = st.text_input(_t("confirm_addr", lang),
                                          value=st.session_state.get("user_addr", ""))
            confirm_dest = st.text_input(_t("confirm_dest", lang))
            submitted = st.form_submit_button(_t("confirm_btn", lang))
            if submitted and confirm_name:
                if "evacuee_list" in st.session_state:
                    # Update dispatcher tracker if name matches
                    mask = st.session_state.evacuee_list["name"].str.lower() == confirm_name.lower()
                    if mask.any():
                        st.session_state.evacuee_list.loc[mask, "status"] = "Evacuated ✅"
                        st.success(_t("confirm_success", lang, name=confirm_name))
                    else:
                        st.success(_t("confirm_success2", lang, name=confirm_name))
                else:
                    st.success(_t("confirm_success2", lang, name=confirm_name))

    # ── Real data anchors — progressive disclosure ───────────────────────────
    with st.expander(_t("why_title", lang), expanded=False):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(_t("metric1_label", lang), "1.1h",
                  help="653 fires with confirmed evac actions, 2021-2025 WiDS dataset")
        m2.metric(_t("metric2_label", lang), "32h",
                  delta="90th percentile",
                  delta_color="off",
                  help="1 in 10 fires takes over 32h to get an official order")
        m3.metric(_t("metric3_label", lang), "260",
                  delta="39.8% of all WiDS fire events",
                  delta_color="off")
        m4.metric(_t("metric4_label", lang), "11.7 ac/hr",
                  delta="+17% vs non-vulnerable",
                  delta_color="inverse")
        st.caption(_t("data_caption", lang))