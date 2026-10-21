import urllib.request
import urllib.parse
import json
import math
import webbrowser

def get_current_location():
    """IP 기반으로 현재 대략적인 위치(위도, 경도)를 가져옵니다."""
    try:
        with urllib.request.urlopen("http://ip-api.com/json/", timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('status') == 'success':
                return data.get('lat'), data.get('lon'), data.get('city')
    except:
        pass
    return 37.5665, 126.9780, "Seoul"

def calculate_distance(lat1, lon1, lat2, lon2):
    """두 좌표 사이의 거리를 km 단위로 계산합니다."""
    R = 6371
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2) * math.sin(dLat / 2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLon / 2) * math.sin(dLon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def _fetch_photon(query, lat, lon):
    results = []
    try:
        # Photon API
        url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(query)}&limit=10&lat={lat}&lon={lon}&lang=ko"
        headers = {"User-Agent": "GeminiCalendarWidget/1.4"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for feature in data.get('features', []):
                coords = feature['geometry']['coordinates']
                props = feature['properties']
                results.append({
                    'name': props.get('name', ''),
                    'address': " ".join([p for p in [props.get('state', ''), props.get('city', ''), props.get('district', ''), props.get('street', '')] if p]),
                    'lat': coords[1],
                    'lng': coords[0],
                    'distance': calculate_distance(lat, lon, coords[1], coords[0])
                })
    except:
        pass
    return results

def geocode_list(query, user_lat=None, user_lon=None):
    if not query: return []
    if user_lat is None or user_lon is None:
        user_lat, user_lon, _ = get_current_location()

    # 1. 띄어쓰기 정제 및 여러 변형으로 검색
    search_terms = [f"{query} 대한민국", query]
    if " " not in query and len(query) > 2:
        search_terms.append(f"{query[:2]} {query[2:]}") # 예: 더기운 -> 더 기운
    
    all_results = []
    for term in search_terms:
        all_results.extend(_fetch_photon(term, user_lat, user_lon))
        if len(all_results) >= 5: break

    # 중복 제거 및 거리순 정렬
    seen = set()
    unique_results = []
    for r in all_results:
        key = (round(r['lat'], 4), round(r['lng'], 4))
        if key not in seen:
            seen.add(key)
            r['display'] = f"{r['name']} ({r['address']}) - {r['distance']:.1f}km"
            unique_results.append(r)
            
    unique_results.sort(key=lambda x: x['distance'])
    return unique_results

def open_google_maps_search(query):
    """검색어가 없을 경우 브라우저에서 구글 지도를 열어줍니다."""
    url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
    webbrowser.open(url)
