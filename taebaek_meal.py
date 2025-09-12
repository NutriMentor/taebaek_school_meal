import requests
import pandas as pd
import re
import urllib3
import streamlit as st
from datetime import datetime
import locale

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
            # 알레르기 정보 제거
            dish_info_cleaned = re.sub(r'\s*\([^)]*\d[^)]*\)', '', dish_info)
            # <br/> 태그로 분리하여 리스트로 변환
            dishes = [d.strip() for d in dish_info_cleaned.split('<br/>') if d.strip()]
            return dishes
    except Exception as e:
        return ["정보를 불러오는 데 실패했습니다."]
    return ["정보가 없습니다."]

def create_school_menu_table(school_data, meal_name):
    """학교 급식 데이터를 HTML 테이블로 생성합니다."""
    # 학교급별로 그룹화
    categories = {}
    for data in school_data:
        category = data['학교급']
        if category not in categories:
            categories[category] = []
        categories[category].append(data)

    # 테이블 HTML 생성 시작
    html = '''
    <div style="margin: 20px 0; overflow-x: auto; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
        <table style="width: 100%; border-collapse: collapse; font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; background: white;">
    '''

    # 학교급 헤더 생성
    html += '<tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">'
    html += '<th style="border: 1px solid #ddd; padding: 15px; text-align: center; font-size: 16px; font-weight: bold; position: sticky; left: 0; z-index: 10; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">구분</th>'

    category_order = ["초등학교", "중학교", "고등학교", "특수학교", "기타"]
    for category in category_order:
        if category in categories:
            school_count = len(categories[category])
            html += f'<th colspan="{school_count}" style="border: 1px solid #ddd; padding: 15px; text-align: center; font-size: 16px; font-weight: bold;">{category}</th>'

    html += '</tr>'

    # 학교명 헤더 생성
    html += '<tr style="background-color: #f8f9ff;">'
    html += f'<th style="border: 1px solid #ddd; padding: 12px; text-align: center; font-size: 14px; font-weight: bold; position: sticky; left: 0; z-index: 9; background-color: #f8f9ff;">{meal_name}</th>'

    for category in category_order:
        if category in categories:
            for school_info in categories[category]:
                # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
                # [수정됨] .replace('고', '') 를 삭제하여 '~~~고'로 올바르게 표시
                school_name = school_info['학교명'].replace('학교', '').replace('등', '')  # 간소화된 표시
                # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
                html += f'<th style="border: 1px solid #ddd; padding: 8px; text-align: center; font-size: 13px; font-weight: bold; min-width: 140px; max-width: 160px; word-break: keep-all;">{school_name}</th>'

    html += '</tr>'

    # 메뉴 데이터 행 생성
    html += '<tr>'
    html += f'<td style="border: 1px solid #ddd; padding: 15px; text-align: center; font-weight: bold; background-color: #f0f2f6; position: sticky; left: 0; z-index: 8; font-size: 14px;">{meal_name} 메뉴</td>'

    for category in category_order:
        if category in categories:
            for school_info in categories[category]:
                menu_list = school_info['메뉴']
                if isinstance(menu_list, list):
                    menu_html = ""
                    for i, menu_item in enumerate(menu_list):
                        if i > 0:
                            menu_html += "<br>"
                        menu_html += f'<span style="display: block; margin: 2px 0; padding: 1px 4px; background-color: rgba(102, 126, 234, 0.1); border-radius: 3px; font-size: 13px;">{menu_item}</span>'
                else:
                    menu_html = f'<span style="color: #e74c3c; font-weight: bold;">{menu_list}</span>'
                html += f'<td style="border: 1px solid #ddd; padding: 12px; text-align: center; vertical-align: top; line-height: 1.4; font-size: 13px; background-color: #ffffff;">{menu_html}</td>'

    html += '</tr>'
    html += '</table></div>'
    return html

# --- Streamlit UI ---
st.set_page_config(page_title="태백지역 학교 급식 메뉴", layout="wide", initial_sidebar_state="collapsed")

# (스타일 부분은 이전과 동일하여 생략)
st.markdown("""
<style>
...
</style>
""", unsafe_allow_html=True)


# 페이지 제목
st.markdown("""
<h1 style="text-align: center; color: #2c3e50; margin-bottom: 2rem; font-size: 2.5rem; font-weight: bold;">
    🏫 태백 학교 급식 메뉴 조회
</h1>
""", unsafe_allow_html=True)

st.markdown("---")

# 날짜 및 식사 선택
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    selected_date = st.date_input(
        "📅 조회할 날짜를 선택하세요",
        value=datetime.now(),
        help="조회하고자 하는 급식 날짜를 선택해주세요."
    )
    
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
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
        
        with st.spinner(f'{selected_date.strftime("%m월 %d일")} {selected_meal_name} 급식 정보를 가져오는 중입니다...'):
            meal_results = []
            progress_bar = st.progress(0, text="조회 시작...")
            total_schools = len(TAEBAEK_SCHOOLS)

            for i, school_name in enumerate(TAEBAEK_SCHOOLS):
                progress_text = f"{school_name} 조회 중... ({i+1}/{total_schools})"
                progress_bar.progress((i + 1) / total_schools, text=progress_text)
                
                category = get_school_category(school_name)
                school_code = search_school_code(OFFICE_CODE, school_name)
                
                if school_code:
                    menu = fetch_meal_menu(OFFICE_CODE, school_code, date_to_fetch_str, selected_meal_code)
                    meal_results.append({'학교급': category, '학교명': school_name, '메뉴': menu})
                else:
                    meal_results.append({'학교급': category, '학교명': school_name, '메뉴': ["❌ 학교 코드를 찾을 수 없습니다."]})

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
                
                table_html = create_school_menu_table(schools_with_menus, selected_meal_name)
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
    
# 사용법 및 정보
st.markdown("---")

# 정보 섹션
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    ### 📋 사용법
    1. **날짜 선택**: 조회하고 싶은 날짜를 선택하세요
    2. **조회하기**: '메뉴 조회하기' 버튼을 클릭합니다
    3. **결과 확인**: 각 학교별 메뉴를 확인할 수 있습니다
    4. **스크롤**: 테이블이 넓을 경우 좌우 스크롤로 확인합니다
    
    ### 💡 특징
    - **실시간 조회**: 나이스 교육정보 개방포털 연동
    - **세로 메뉴 표시**: 각 메뉴 항목이 세로로 깔끔하게 정렬
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

# 푸터
st.markdown("""
<div style="text-align: center; color: #7f8c8d; margin-top: 2rem; font-size: 14px;">
    <p>🍚 태백지역 학교 급식 메뉴 통합 조회 서비스 | Made by 권영우</p>
</div>
""", unsafe_allow_html=True)






