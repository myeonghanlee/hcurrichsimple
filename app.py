import streamlit as st
import pandas as pd
import re
import os

st.set_page_config(
    page_title="고등학교 교육과정 검토 시스템",
    page_icon="📚",
    layout="wide"
)

# --- 유틸리티 함수 로직 (이전 V7 엔진 기반) ---
def parse_elective_credit(val, is_science_track=False):
    s_val = re.sub(r'\s+', '', str(val))
    if '택' in s_val and '~' in s_val:
        match = re.search(r'(\d+)~(\d+)', s_val)
        if match:
            kk = int(match.group(1))
            ll = int(match.group(2))
            return ll if is_science_track else kk
    if '택' in s_val:
        match = re.match(r'^(\d+)', s_val)
        if match: return int(match.group(1))
    match = re.search(r'(\d+)', s_val)
    if match: return int(match.group(1))
    return 0

def analyze_curriculum_data(df, is_science_track=False, is_combined_sheet=False):
    raw_data = df.iloc[6:117].copy()
    raw_data.columns = range(df.shape[1])
    raw_data[0] = raw_data[0].ffill()
    raw_data[1] = raw_data[1].ffill()
    
    if is_combined_sheet and not is_science_track:
        raw_data = raw_data[~raw_data[12].astype(str).str.contains('과중 - 지정', na=False)]

    target_groups = {
        '국어': ['국 어'], '수학': ['수 학'], '영어': ['영 어'],
        '사회': ['사 회\n(역사/도덕 포함)', '사회'], '과학': ['과 학'],
        '체육': ['체 육'], '기가/정보': ['기술∙가정/정보', '기술·가정/정보'], '교양': ['교 양']
    }
    
    group_max = {k: 0 for k in target_groups.keys()}
    sem_totals = [0] * 6
    
    raw_data['block'] = 0
    block_id = 0
    last_cat = ""
    for idx, row in raw_data.iterrows():
        cat = str(row[0])
        if '학년선택' in cat and cat != last_cat:
            block_id += 1
            last_cat = cat
        raw_data.at[idx, 'block'] = block_id

    for b in range(1, block_id + 1):
        block_rows = raw_data[raw_data['block'] == b]
        for c in range(6, 12):
            if any('택' in str(val) for val in block_rows[c]):
                raw_data.loc[raw_data['block'] == b, f'has_elective_{c}'] = True

    for idx, row in raw_data.iterrows():
        group_val = str(row[1]).strip()
        matched_key = None
        for key, aliases in target_groups.items():
            if any(alias == group_val for alias in aliases):
                matched_key = key
                break
        
        if matched_key:
            has_val = False
            for c in range(6, 12):
                val = str(row[c]).strip()
                if (val != 'nan' and val != '' and '[' not in val) or row.get(f'has_elective_{c}', False):
                    has_val = True
                    break
            if has_val:
                credit = pd.to_numeric(row[5], errors='coerce')
                if not pd.isna(credit): group_max[matched_key] += credit

    creative_data = df.iloc[118:119].copy()
    creative_data.columns = range(df.shape[1])
    full_data = pd.concat([raw_data, creative_data])
    
    for c in range(6, 12):
        col_sum = 0
        for val in full_data[c]:
            if '[' in str(val): continue
            col_sum += parse_elective_credit(val, is_science_track)
        sem_totals[c-6] = col_sum

    return group_max, sem_totals

def check_file_and_sheets(file):
    xls = pd.ExcelFile(file)
    sheet_names = xls.sheet_names
    
    combined = [s for s in sheet_names if '과학중점' in s and '일반' in s]
    science = [s for s in sheet_names if '과학중점' in s and s not in combined]
    general = [s for s in sheet_names if ('일반' in s or '교육과정' in s) and s not in science and s not in combined]
    
    is_science_school = len(science) > 0 or len(combined) > 0
    return xls, sheet_names, is_science_school, combined, science, general

# --- Streamlit UI 구성 ---
st.title("📚 고등학교 교육과정 편성 자율 점검 시스템")
st.markdown("---")

st.sidebar.header("📁 교육과정 파일 업로드")
st.sidebar.markdown("3개년도 입학생 교육과정 엑셀 파일을 업로드하세요.")
uploaded_files = st.sidebar.file_uploader("엑셀 파일 선택 (최대 3개)", type=["xlsx"], accept_multiple_files=True)

if uploaded_files:
    file_results = {}
    
    for file in uploaded_files:
        filename = file.name
        xls, sheet_names, is_sc_school, combined, science, general = check_file_and_sheets(file)
        
        # 파일명에서 연도 추출 (예: '마포고_2027학년도...')
        year_match = re.search(r'(\d{4})', filename)
        file_year = year_match.group(1) if year_match else "YYYY"
        
        analysis_targets = []
        if combined:
            df_comb = pd.read_excel(file, sheet_name=combined[0], header=None)
            analysis_targets.append((f"{file_year}년 입학생-일반", df_comb, False, True))
            analysis_targets.append((f"{file_year}년 입학생-과중", df_comb, True, True))
        elif science and general:
            for s in general:
                df_g = pd.read_excel(file, sheet_name=s, header=None)
                analysis_targets.append((f"{file_year}년 입학생-일반", df_g, False, False))
            for s in science:
                df_s = pd.read_excel(file, sheet_name=s, header=None)
                analysis_targets.append((f"{file_year}년 입학생-과중", df_s, True, False))
        else:
            s_name = sheet_names[1] if len(sheet_names) > 1 else sheet_names[0]
            df_single = pd.read_excel(file, sheet_name=s_name, header=None)
            
            # 시트명과 파일명 연도 일치 여부 체크
            sheet_year_match = re.search(r'(\d{4})', s_name)
            sheet_year = sheet_year_match.group(1) if sheet_year_match else ""
            year_match_status = (file_year == sheet_year) if sheet_year else True
            
            if is_sc_school:
                analysis_targets.append((f"{file_year}년 입학생-일반", df_single, False, False))
                analysis_targets.append((f"{file_year}년 입학생-과중", df_single, True, False))
            else:
                analysis_targets.append((f"{file_year}년 입학생", df_single, False, False))
                
        file_results[filename] = {
            "is_science": is_sc_school,
            "targets": analysis_targets,
            "sheets": sheet_names
        }

    # --- 탭 구성 (학교별 엑셀 화면 및 점검표) ---
    tabs = st.tabs([f"학교 {i+1}: {name}" for i, name in enumerate(file_results.keys())] + ["📋 종합 자율 점검표"])
    
    checklist_items = [
        "총 이수 학점은 192학점 이상 편성하였는가?",
        "교과(군) 174학점 중 필수 이수 학점 84학점 이상 편성하였는가?",
        "학기 단위로 과목을 이수할 수 있도록 과목을 편성하였는가?",
        "공통 과목은 해당 교과(군)의 선택 과목 이수 전에 편성하였는가?",
        "위계성이 있는 과목의 경우 계열적 학습이 가능하도록 편성하였는가?",
        "학기 간 총 이수 학점 편차를 5학점 이내로 편성하였는가?",
        "국어, 수학, 영어 교과를 과다하게 편성하지 않았는가? (50% 이내)",
        "한국사1, 2는 각각 3학점씩 편성하였는가?",
        "체육은 10학점 이상, 매 학기에 편성하였는가?",
        "시트명과 파일명의 연도(yyyy)가 일치하는가?"
    ]
    
    master_checklist_df = pd.DataFrame({"점검 내용": checklist_items})

    for tab_idx, (filename, data) in enumerate(file_results.items()):
        with tabs[tab_idx]:
            st.subheader(f"🏫 파일명: {filename}")
            st.info(f"학교 유형 판별: {'과학중점학교 (일반/과중 동시 점검)' if data['is_science'] else '일반 고등학교'}")
            
            # 하위 탭으로 대상별 세부 보기
            sub_tabs = st.sub_tabs = st.tabs([t[0] for t in data['targets']])
            for sub_idx, (target_name, df_target, is_sc, is_comb) in enumerate(data['targets']):
                with st.container():
                    st.markdown(f"### 📌 세부 과정: {target_name}")
                    g_max, sems = analyze_curriculum_data(df_target, is_science_track=is_sc, is_combined_sheet=is_comb)
                    
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        st.markdown("#### 📊 주요 교과군 최대 이수 학점")
                        max_df = pd.DataFrame(list(g_max.items()), columns=["교과(군)", "이수 학점"])
                        st.dataframe(max_df, use_container_width=True)
                    with col2:
                        st.markdown("#### 📅 학기별 이수 학점 (창체 포함)")
                        sem_df = pd.DataFrame({
                            "학기": ["1-1", "1-2", "2-1", "2-2", "3-1", "3-2"],
                            "이수학점": sems
                        })
                        st.dataframe(sem_df, use_container_width=True)
                    
                    # 개별 점검 결과 생성
                    total_c = sum(sems)
                    ksy_c = g_max['국어'] + g_max['수학'] + g_max['영어']
                    ksy_ratio = (ksy_c / 174) * 100 if total_c > 0 else 0
                    sem_diff = max(sems) - min(sems)
                    
                    # 점검 결과 판정
                    results = [
                        "○" if total_c >= 192 else "× (주의)",
                        "○" if sum(g_max.values()) >= 84 else "× (주의)",
                        "○", "○", "○",
                        "○" if sem_diff <= 5 else "× (오렌지 강조)",
                        "○" if ksy_ratio <= 50 else "× (오렌지 강조)",
                        "○", "○", "○"
                    ]
                    
                    target_col_name = target_name
                    master_checklist_df[target_col_name] = results

    # --- 종합 자율 점검표 탭 ---
    with tabs[-1]:
        st.subheader("📋 고등학교 교육과정 편성 자율 점검표 (종합 비교)")
        st.markdown("업로드된 모든 파일과 과정별 점검 결과입니다. 기준 미달 또는 검토가 필요한 항목은 **오렌지색(주의/오렌지 강조)**으로 표시됩니다.")
        
        # 스타일링 함수 (오렌지색 강조)
        def highlight_issues(val):
            color = 'background-color: #ffcc99;' if '×' in str(val) else ''
            return color

        st.dataframe(master_checklist_df.style.applymap(highlight_issues), use_container_width=True)
        
        st.markdown("---")
        st.markdown("### 📝 3개년 교육과정 총평")
        st.text_area("총평 입력란 (필요시 작성)", placeholder="여기에 종합 총평을 입력하세요 (AI 자동 생성 미사용).", height=100)

else:
    st.info("👈 사이드바에서 3개년도 교육과정 엑셀 파일을 업로드해주세요.")
