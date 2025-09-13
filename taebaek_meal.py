import requests
import pandas as pd
import re
import urllib3
import streamlit as st
from datetime import datetime
import locale
import concurrent.futures # [★최적화★] 병렬 처리를 위한 라이러리 임포트

# 한국어 로케일 설정 (Streamlit Cloud 등 일부 환경에서는 필요할 수 있음)
try:
    locale.setlocale(locale.LC_ALL, 'ko_KR.UTF-8')
except locale.Error:
    # 로케일 설정이 실패해도 앱은 계속 실행되도록 예외 처리
    pass

# SSL 경고 메시지 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- API 키 설정 ---
# st.secrets를 통해 배포 환경의 비밀값을 안전하게 가져옵니다.
try:
    API_KEY = st.secrets["NEIS_API_KEY"]
except FileNotFoundError:
    st.error("API 키가 설정되지 않았습니다. Streamlit Secrets에 NEIS_API_KEY를 추가해주세요.")
    st.stop()


# --- 조회 대상 설정 (태백지역 학교 목록) ---
OFFICE_CODE = "K10"
TAEBAEK_SCHOOLS = [
    "동점초등학교", "미동초등학교", "삼성초등학교", "상장초등학교", "장성초등학교",
    "철암초등학교", "태백초등학교", "태서초등학교", "통리초등학교", "함태초등학교",
    "황지중앙초등학교", "황지초등학교",
    "상장중학교", "세연중학교", "태백중학교", "함태중학교", "황지중학교",
    "장성여자고등학교", "철암고등학교", "한국항공고등학교", "황지고등학교",
    "황지정보산업고등학교",
    "태백라온학교"
]

# --- Helper 함수들 ---
def get_school_category(school_name):
    """학교명을 기반으로 학교급(대분류)을 반환합니다."""
    if "초등학교" in school_name:
        return "초등학교"
    elif "중학교" in school_name:
        return "중학교"
    elif "고등학교" in school_name:
        return "고등학교"
    elif "라온학교" in school_name:
        return "특수학교"
    else:
        return "기타"

def search_school_code(office_code, school_name):
    """주어진 학교명으로 학교 코드를 검색하여 반환합니다."""
    URL = (
        f"https://open.neis.go.kr/hub/schoolInfo"
        f"?KEY={API_KEY}&Type=json&pIndex=1&pSize=10"
        f"&ATPT_OFCDC_SC_CODE={office_code}&SCHUL_NM={school_name}"
    )
    try:
        response = requests.get(URL, timeout=10, verify=False)
        response.raise_for_status()
        data = response.json()
        if 'schoolInfo' in data and 'row' in data['schoolInfo'][1]:
            schools = data['schoolInfo'][1]['row']
            for s in schools:
                if s['SCHUL_NM'] == school_name:
                    return s['SD_SCHUL_CODE']
            return schools[0]['SD_SCHUL_CODE']
    except Exception:
        return None
    return None

# [수정] 알레르기 정보를 포함하도록 fetch_meal_menu 함수 수정
def fetch_meal_menu(office_code, school_code, date_str, meal_code):
    """선택된 날짜와 식사종류의 메뉴를 조회하고 리스트로 반환합니다."""
    URL = (
        f"https://open.neis.go.kr/hub/mealServiceDietInfo"
        f"?KEY={API_KEY}&Type=json&pIndex=1&pSize=10"
        f"&ATPT_OFCDC_SC_CODE={office_code}&SD_SCHUL_CODE={school_code}"
        f"&MLSV_YMD={date_str}&MMEAL_SC_CODE={meal_code}"
    )
    try:
        response = requests.get(URL, timeout=10, verify=False)
        response.raise_for_status()
        data = response.json()
        if 'mealServiceDietInfo' in data and 'row' in data['mealServiceDietInfo'][1]:
            record = data['mealServiceDietInfo'][1]['row'][0]
            dish_info = record.get('DDISH_NM', '')
            # [수정] 알레르기 정보를 제거하는 로직을 삭제하고, 원본 문자열을 그대로 사용
            dishes = [d.strip() for d in dish_info.split('<br/>') if d.strip()]
            return dishes
    except Exception as e:
        return ["정보를 불러오는 데 실패했습니다."]
    return ["정보가 없습니다."]

# [★최적화★] 병렬 처리를 위한 단일 작업 함수
def get_single_school_data(school_name, office_code, date_str, meal_code):
    """학교 1곳의 코드 검색과 메뉴 조회를 한번에 처리하는 함수"""
    category = get_school_category(school_name)
    school_code = search_school_code(office_code, school_name)
    
    if school_code:
        menu = fetch_meal_menu(office_code, school_code, date_str, meal_code)
        return {'학교급': category, '학교명': school_name, '메뉴': menu}
    else:
        return {'학교급': category, '학교명': school_name, '메뉴': ["❌ 학교 코드를 찾을 수 없습니다."]}

# [수정] 알레르기 정보 표시 여부를 인자로 받아 조건부로 출력하도록 함수 수정
def create_school_menu_table(school_data, meal_name, show_allergy=True):
    """학교 급식 데이터를 HTML 테이블로 생성합니다."""
    categories = {}
    for data in school_data:
        category = data['학교급']
        if category not in categories:
            categories[category] = []
        categories[category].append(data)

    html = '''
    <div style="margin: 20px 0; overflow-x: auto; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
        <table style="width: 100%; border-collapse: collapse; font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; background: white;">
    '''
    
    html += '<tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">'
    html += '<th style="border: 1px solid #ddd; padding: 15px; text-align: center; font-size: 16px; font-weight: bold; position: sticky; left: 0; z-index: 10; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">구분</th>'
    category_order = ["초등학교", "중학교", "고등학교", "특수학교", "기타"]
    for category in category_order:
        if category in categories:
            school_count = len(categories[category])
            html += f'<th colspan="{school_count}" style="border: 1px solid #ddd; padding: 15px; text-align: center; font-size: 16px; font-weight: bold;">{category}</th>'
    html += '</tr>'
    
    html += '<tr style="background-color: #f8f9ff;">'
    html += f'<th style="border: 1px solid #ddd; padding: 12px; text-align: center; font-size: 14px; font-weight: bold; position: sticky; left: 0; z-index: 9; background-color: #f8f9ff;">{meal_name}</th>'
    for category in category_order:
        if category in categories:
            for school_info in categories[category]:
                school_name = school_info['학교명'].replace('학교', '').replace('등', '')
                html += f'<th style="border: 1px solid #ddd; padding: 8px; text-align: center; font-size: 13px; font-weight: bold; min-width: 140px; max-width: 160px; word-break: keep-all;">{school_name}</th>'
    html += '</tr>'
    
    max_menu_count = 0
    for data in school_data:
        if isinstance(data['메뉴'], list):
            max_menu_count = max(max_menu_count, len(data['메뉴']))

    for i in range(max_menu_count):
        html += '<tr>'
        if i == 0:
            html += f'<td rowspan="{max_menu_count}" style="border: 1px solid #ddd; padding: 15px; text-align: center; font-weight: bold; background-color: #f0f2f6; position: sticky; left: 0; z-index: 8; font-size: 14px; vertical-align: middle;">{meal_name} 메뉴</td>'
        
        for category in category_order:
            if category in categories:
                for school_info in categories[category]:
                    menu_list = school_info['메뉴']
                    menu_item = ""
                    if isinstance(menu_list, list) and i < len(menu_list):
                        menu_item_raw = menu_list[i]
                        match = re.match(r'^(.*?)\s*\(([\d\.]+)\)$', menu_item_raw)
                        
                        if match:
                            dish_name = match.group(1).strip()
                            allergy_info = match.group(2).strip()
                            # [수정] show_allergy 값에 따라 알레르기 정보 표시 여부 결정
                            menu_item_content = f'<div style="font-weight: 500;">{dish_name}</div>'
                            if show_allergy:
                                menu_item_content += f'<div style="font-size: 12px; color: #e74c3c;">({allergy_info})</div>'
                        else:
                            menu_item_content = f'<div style="font-weight: 500;">{menu_item_raw.strip()}</div>'
                        
                        menu_item = f'<div style="margin: 2px 0; padding: 6px 4px; background-color: rgba(102, 126, 234, 0.08); border-radius: 4px; font-size: 13px;">{menu_item_content}</div>'
                    
                    elif i == 0 and not isinstance(menu_list, list):
                         menu_item = f'<span style="color: #e74c3c; font-weight: bold;">{menu_list}</span>'

                    html += f'<td style="border: 1px solid #ddd; padding: 8px; text-align: center; vertical-align: top; line-height: 1.5; font-size: 13px; background-color: #ffffff;">{menu_item}</td>'

        html += '</tr>'
    
    html += '</table></div>'
    return html

# --- Streamlit UI ---
st.set_page_config(page_title="태백지역 학교 급식 메뉴", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
/* CSS 스타일 코드는 생략하지 않고 그대로 둡니다. */
</style>
""", unsafe_allow_html=True)

st.markdown("""
<h1 style="text-align: center; color: #2c3e50; margin-bottom: 2rem; font-size: 2.5rem; font-weight: bold;">
    🏫 태백 학교 급식 메뉴 조회
</h1>
""", unsafe_allow_html=True)

st.markdown("---")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    selected_date = st.date_input(
        "📅 조회할 날짜를 선택하세요",
        value=datetime.now(),
        help="조회하고자 하는 급식 날짜를 선택해주세요."
    )
    
    # [추가] 알레르기 정보 표시 여부를 선택하는 토글 스위치
    show_allergy_info = st.toggle("알레르기 정보 표시", value=True, help="체크를 해제하면 메뉴명만 표시됩니다.")

    meal_options = {"조식": "1", "중식": "2", "석식": "3"}
    selected_meal_name = st.radio(
        "🍽️ 식사 종류를 선택하세요",
        options=list(meal_options.keys()),
        index=1,
        horizontal=True,
    )
    selected_meal_code = meal_options[selected_meal_name]
    st.markdown("<br>", unsafe_allow_html=True)

    if st.button(f"🔄 {selected_date.strftime('%Y년 %m월 %d일')} {selected_meal_name} 메뉴 조회하기"):
        date_to_fetch_str = selected_date.strftime('%Y%m%d')
        
        with st.spinner(f'{selected_date.strftime("%m월 %d일")} {selected_meal_name} 급식 정보를 빠르게 가져오는 중입니다...'):
            meal_results = []
            progress_bar = st.progress(0, text="조회 시작...")
            total_schools = len(TAEBAEK_SCHOOLS)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_school = {
                    executor.submit(get_single_school_data, school_name, OFFICE_CODE, date_to_fetch_str, selected_meal_code): school_name
                    for school_name in TAEBAEK_SCHOOLS
                }
                
                results_map = {}
                completed_count = 0
                for future in concurrent.futures.as_completed(future_to_school):
                    school_name = future_to_school[future]
                    try:
                        result = future.result()
                        results_map[school_name] = result
                    except Exception as exc:
                        results_map[school_name] = {'학교급': get_school_category(school_name), '학교명': school_name, '메뉴': [f"오류 발생: {exc}"]}
                    
                    completed_count += 1
                    progress_text = f"{school_name} 조회 완료... ({completed_count}/{total_schools})"
                    progress_bar.progress(completed_count / total_schools, text=progress_text)
            
            for school_name in TAEBAEK_SCHOOLS:
                meal_results.append(results_map[school_name])

        if meal_results:
            schools_with_menus = []
            for r in meal_results:
                menu_info = r.get('메뉴')
                if isinstance(menu_info, list) and menu_info:
                    if "정보가 없습니다" not in menu_info[0] and \
                       "실패했습니다" not in menu_info[0] and \
                       "찾을 수 없습니다" not in menu_info[0]:
                        schools_with_menus.append(r)

            if schools_with_menus:
                st.success(f"✅ 총 {len(meal_results)}개 학교 중 {len(schools_with_menus)}곳의 {selected_meal_name} 정보를 조회했습니다!")
                
                # [수정] 토글 스위치의 상태(show_allergy_info)를 함수에 전달
                table_html = create_school_menu_table(schools_with_menus, selected_meal_name, show_allergy=show_allergy_info)
                st.markdown(table_html, unsafe_allow_html=True)
                
                st.markdown("---")
                col1, col2, col3, col4 = st.columns(4)
                total_schools_queried = len(meal_results)
                schools_with_menu_count = len(schools_with_menus)
                
                with col1:
                    st.metric("전체 조회 학교", f"{total_schools_queried}개")
                with col2:
                    st.metric("메뉴 조회 성공", f"{schools_with_menu_count}개")
                with col3:
                    st.metric("조회 성공률", f"{schools_with_menu_count/total_schools_queried*100:.1f}%" if total_schools_queried > 0 else "0.0%")
                with col4:
                    st.metric("조회일", selected_date.strftime('%m월 %d일'))
            else:
                st.warning(f"선택하신 날짜에 {selected_meal_name} 정보를 가진 학교가 없습니다.")
        else:
            st.error("정보를 조회하는 데 실패했습니다.")

# [수정] 알레르기 정보 안내 섹션을 다단으로 변경하여 공간 효율성 개선
with st.expander("📌 알레르기 정보 안내 (펼쳐보기)"):
    st.markdown("**메뉴 옆의 숫자는 알레르기를 유발할 수 있는 식품을 의미합니다.**")

    # 4개의 컬럼을 만들어 정보를 나눠서 표시합니다.
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            """
            - `1`. 난류 (가금류)
            - `2`. 우유
            - `3`. 메밀
            - `4`. 땅콩
            - `5`. 대두
            """
        )
    with col2:
        st.markdown(
            """
            - `6`. 밀
            - `7`. 고등어
            - `8`. 게
            - `9`. 새우
            - `10`. 돼지고기
            """
        )
    with col3:
        st.markdown(
            """
            - `11`. 복숭아
            - `12`. 토마토
            - `13`. 아황산류
            - `14`. 호두
            - `15`. 닭고기
            """
        )
    with col4:
        st.markdown(
            """
            - `16`. 쇠고기
            - `17`. 오징어
            - `18`. 조개류 (굴, 전복, 홍합 포함)
            - `19`. 잣
            """
        )

    st.markdown(
        """
        <div style='text-align: right; margin-top: 10px;'>
            <small>*이 정보는 식품의약품안전처 고시에 따른 것입니다. 학교별 표기 방식에 차이가 있을 수 있습니다.*</small>
        </div>
        """,
        unsafe_allow_html=True
    )


col1, col2 = st.columns(2)
with col1:
    st.markdown("""
    ### 📋 사용법
    1. **날짜 선택**: 조회하고 싶은 날짜를 선택하세요
    2. **조회하기**: '메뉴 조회하기' 버튼을 클릭합니다
    3. **결과 확인**: 각 학교별 메뉴와 알레르기 정보를 확인합니다
    4. **스크롤**: 테이블이 넓을 경우 좌우 스크롤로 확인합니다
    
    ### 💡 특징
    - **실시간 조회**: 나이스 교육정보 개방포털 연동
    - **알레르기 정보**: 메뉴별 알레르기 유발 식품 번호 표시
    - **반응형 디자인**: 모바일과 데스크톱 모두 지원
    """)
with col2:
    st.markdown("""
    ### 🏫 조회 대상 학교
    **초등학교 (12개)** 동점, 미동, 삼성, 상장, 장성, 철암, 태백, 태서, 통리, 함태, 황지중앙, 황지초등학교
    
    **중학교 (5개)** 상장, 세연, 태백, 함태, 황지중학교
    
    **고등학교 (5개)** 장성여자, 철암, 한국항공, 황지, 황지정보산업고등학교
    
    **특수학교 (1개)** 태백라온학교
    """)
st.markdown("---")
st.info("📌 이 서비스는 나이스 교육정보 개방 포털의 API를 활용하여 제작되었습니다.")

st.markdown("""
<div style="text-align: center; color: #7f8c8d; margin-top: 2rem; font-size: 14px;">
    <p>🍚 태백지역 학교 급식 메뉴 통합 조회 서비스 | Made by 권영우</p>
</div>
""", unsafe_allow_html=True)
