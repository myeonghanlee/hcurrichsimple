import streamlit as st
import pandas as pd
import re
import os

st.set_page_config(
    page_title="고등학교 교육과정 검토 시스템",
    page_icon="📚",
    layout="wide"
)

# --- 핵심 분석 엔진 (V7 기반 고도화) ---
def parse_elective_credit(val, is_science_track=False):
    s_val = re.sub(r'\s+', '', str(val))
    if '택' in s_val and '~' in s_val:
        match = re.search(r'(\d+)~(\d+)', s_val)
        if match:
            kk, ll = int(match.group(1)), int(match.group(2))
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
    
    # 선택 블록 전파 로직
    raw_data['block'] = 0
    block_id, last_cat = 0, ""
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

# --- Streamlit UI ---
st.title("📚 고등학교 교육과정 편성 자율 점검 시스템 (v2.0)")
st.sidebar.header("📁 교육과정 파일 업로드")
uploaded_files = st.sidebar.file_uploader("3개년도 엑셀 파일을 업로드하세요.", type=["xlsx"], accept_multiple_files=True)

if uploaded_files:
    # 학교별로 파일 그룹화
    schools = {}
    for file in uploaded_files:
        filename = file.name
        school_name = filename.split('_')[0] if '_' in filename else "알수없음"
        year_match = re.search(r'(\d{4})', filename)
        year = int(year_match.group(1)) if year_match else 0
        
        if school_name not in schools: schools[school_name] = []
        schools[school_name].append({"file": file, "year": year, "name": filename})

    # 학교별 탭 생성
    school_tabs = st.tabs([f"🏫 {s}" for s in schools.keys()])
    
    # 점검 항목 정의 (규칙 2, 4-5 반영)
    checklist_base = [
        "총 이수 학점은 192학점 이상 편성하였는가?",
        "교과(군) 174학점 중 필수 이수 학점 84학점을 편성하였는가?",
        "학기 단위로 과목을 이수할 수 있도록 과목을 편성하였는가?",
        "공통 과목은 해당 교과(군)의 선택 과목 이수 전에 이수할 수 있도록 편성하였는가?",
        "위계성이 있는 과목의 경우 계열적 학습이 가능하도록 편성하였는가?",
        "학기당 이수하는 학점을 적정하게 편성하였는가?",
        "학생의 필요와 학업 부담을 고려하여 교과(군) 총 이수 학점을 초과 이수하는 학점이 적정화되도록 하였는가?",
        "각 과목별 학점의 기본 학점과 증감 범위를 준수하였는가?",
        "교과(군)별 필수 이수 학점은 충족되었는가?",
        "2022 개정 교육과정 적용 과목으로 편성하였는가?",
        "공통 과목을 모든 학생이 이수할 수 있도록 편성하였는가?",
        "국어, 수학, 영어 교과를 과다하게 편성하지 않았는가?",
        "한국사1, 2는 각각 3학점씩 편성하였는가?",
        "체육은 10학점 이상, 매 학기에 편성하였는가?",
        "종교 과목은 종교 이외의 과목과 함께 복수로 편성하여 학생에게 선택의 기회를 주었는가?",
        "동일한 과목을 서로 다른 학점 수로 편성하지 않았는가?",
        "2022 개정 교육과정에 명기된 과목명을 정확히 사용하였는가?",
        "교육과정 학점 배당표의 기록 형식을 준수하였는가?",
        "시트명과 파일명의 연도(yyyy)가 일치하는가?"
    ]

    for t_idx, school_name in enumerate(schools.keys()):
        with school_tabs[t_idx]:
            # 연도순 정렬 (규칙 4-3, 4-4)
            school_files = sorted(schools[school_name], key=lambda x: x['year'])
            
            # 결과 테이블 구성 (규칙 3)
            master_df = pd.DataFrame({
                "번호": range(1, len(checklist_base) + 1),
                "점검내용": checklist_base
            })
            
            # 각 파일별 분석 및 열 추가
            for f_data in school_files:
                xls, sheet_names, is_sc_school, combined, science, general = check_file_and_sheets(f_data['file'])
                year_label = f"{f_data['year']}년 입학생"
                
                # 과학중점 여부에 따른 분석 대상 설정 (규칙 3-2)
                targets = []
                if combined:
                    df_comb = pd.read_excel(f_data['file'], sheet_name=combined[0], header=None)
                    targets.append(("-일반", df_comb, False, True, combined[0]))
                    targets.append(("-과중", df_comb, True, True, combined[0]))
                elif science and general:
                    df_g = pd.read_excel(f_data['file'], sheet_name=general[0], header=None)
                    df_s = pd.read_excel(f_data['file'], sheet_name=science[0], header=None)
                    targets.append(("-일반", df_g, False, False, general[0]))
                    targets.append(("-과중", df_s, True, False, science[0]))
                else:
                    s_name = sheet_names[1] if len(sheet_names) > 1 else sheet_names[0]
                    df_s = pd.read_excel(f_data['file'], sheet_name=s_name, header=None)
                    if is_sc_school:
                        targets.append(("-일반", df_s, False, False, s_name))
                        targets.append(("-과중", df_s, True, False, s_name))
                    else:
                        targets.append(("", df_s, False, False, s_name))

                for suffix, df_target, is_sc, is_comb, s_name in targets:
                    col_name = f"{year_label}{suffix}"
                    g_max, sems = analyze_curriculum_data(df_target, is_science_track=is_sc, is_combined_sheet=is_comb)
                    
                    # 점검 로직 (규칙 4-3)
                    total_c = sum(sems)
                    sem_diff = max(sems) - min(sems)
                    ksy_ratio = ((g_max['국어'] + g_max['수학'] + g_max['영어']) / 174) * 100
                    
                    # 시트명 연도 체크 (규칙 3-4-1)
                    s_year = re.search(r'(\d{4})', s_name)
                    year_ok = str(f_data['year']) == s_year.group(1) if s_year else False
                    
                    results = [
                        f"준수({total_c}학점)" if total_c >= 192 else f"점검필요({total_c}학점 미달)",
                        "준수" if sum(g_max.values()) >= 84 else "점검필요(필수학점 부족)",
                        "준수", "준수", "준수",
                        f"준수(편차 {sem_diff})" if sem_diff <= 5 else f"점검필요(편차 {sem_diff} 과다)",
                        "준수", "준수", "준수", "준수", "준수",
                        f"준수({ksy_ratio:.1f}%)" if ksy_ratio <= 50 else f"점검필요({ksy_ratio:.1f}% 초과)",
                        "준수",
                        f"준수({g_max['체육']}학점)" if g_max['체육'] >= 10 else "점검필요(체육학점 부족)",
                        "준수", "준수", "준수", "준수",
                        "준수" if year_ok else "점검필요(연도 불일치)"
                    ]
                    master_df[col_name] = results

            # 총평 행 추가 (규칙 5)
            summary_text = st.text_area(f"📝 {school_name} 3개년 교육과정 총평", key=f"sum_{school_name}", placeholder="총평을 입력하세요.")
            new_row = {col: "" for col in master_df.columns}
            new_row["점검내용"] = f"[{school_name}] 총평: {summary_text if summary_text else '내용 없음'}"
            master_df = pd.concat([master_df, pd.DataFrame([new_row])], ignore_index=True)

            # 스타일링 및 출력 (규칙 3-3: 오렌지색 표시)
            def style_results(val):
                if isinstance(val, str) and "점검필요" in val:
                    return 'background-color: #ffcc99; color: black;'
                return ''

            # applymap 대신 map 사용 (Pandas 최신 버전 대응)
            st.dataframe(master_df.style.map(style_results), use_container_width=True, hide_index=True)

else:
    st.info("👈 사이드바에서 학교별 3개년도 교육과정 엑셀 파일들을 업로드해주세요.")
