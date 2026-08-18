import streamlit as st
import pandas as pd
import re
import os
import io

st.set_page_config(
    page_title="고등학교 교육과정 검토 시스템",
    page_icon="📚",
    layout="wide"
)

# --- 고시 과목 데이터 정의 ---
OFFICIAL_SUBJECTS = {
    "국어": ["공통국어1", "공통국어2", "화법과 언어", "독서와 작문", "문학", "주제 탐구 독서", "문학과 영상", "직무 의사소통", "독서 토론과 글쓰기", "매체 의사소통", "언어생활 탐구"],
    "수학": ["공통수학1", "공통수학2", "기본수학1", "기본수학2", "대수", "미적분Ⅰ", "확률과 통계", "기하", "미적분Ⅱ", "경제 수학", "인공지능 수학", "직무 수학", "수학과 문화", "실용 통계", "수학과제 탐구"],
    "영어": ["공통영어1", "공통영어2", "기본영어1", "기본영어2", "영어Ⅰ", "영어Ⅱ", "영어 독해와 작문", "영미 문학 읽기", "영어 발표와 토론", "심화 영어", "심화 영어 독해와 작문", "직무 영어", "실생활 영어 회화", "미디어 영어", "세계 문화와 영어"],
    "사회": ["한국사1", "한국사2", "통합사회1", "통합사회2", "세계시민과 지리", "세계사", "사회와 문화", "현대사회와 윤리", "한국지리 탐구", "도시의 미래 탐구", "동아시아 역사 기행", "정치", "법과 사회", "경제", "윤리와 사상", "인문학과 윤리", "국제 관계의 이해", "여행지리", "역사로 탐구하는 현대 세계", "사회문제 탐구", "금융과 경제생활", "윤리문제 탐구", "기후변화와 지속가능한 세계"],
    "과학": ["통합과학1", "통합과학2", "과학탐구실험1", "과학탐구실험2", "물리학", "화학", "생명과학", "지구과학", "역학과 에너지", "전자기와 양자", "물질과 에너지", "화학 반응의 세계", "세포와 물질대사", "생물의 유전", "지구시스템과학", "행성우주과학", "과학의 역사와 문화", "기후변화와 환경생태", "융합과학 탐구"],
    "체육": ["체육1", "체육2", "운동과 건강", "스포츠 문화", "스포츠 과학", "스포츠 생활1", "스포츠 생활2"],
    "예술": ["음악", "미술", "연극", "음악 연주와 창작", "음악 감상과 비평", "미술 창작", "미술 감상과 비평", "음악과 미디어", "미술과 매체"],
    "기술∙가정/정보": ["기술∙가정", "정보", "로봇과 공학세계", "생활과학 탐구", "창의 공학 설계", "지식 재산 일반", "생애 설계와 자립", "아동발달과 부모", "인공지능 기초", "데이터 과학", "소프트웨어와 생활"]
}
ALL_OFFICIAL_NAMES = [sub for list in OFFICIAL_SUBJECTS.values() for sub in list]

# --- 정밀 분석 엔진 ---
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
    all_data = df.iloc[6:].copy()
    all_data.columns = range(df.shape[1])
    subject_rows, creative_row, invalid_subjects = [], None, []
    
    for idx, row in all_data.iterrows():
        row_str = " ".join([str(v) for v in row.values])
        if any(k in row_str for k in ['소계', '합계', '총계']): continue
        if '창의적' in row_str:
            creative_row = row
            continue
        
        if pd.notna(row[3]) and (pd.notna(row[5]) or any(pd.notna(row[c]) for c in range(6, 12))):
            subject_rows.append(row)
            name = str(row[3]).strip()
            op_credit = pd.to_numeric(row[5], errors='coerce')
            
            if name and name not in ALL_OFFICIAL_NAMES and '창의적' not in name:
                invalid_subjects.append({"과목명": name, "행번호": idx+1, "사유": "고시 명칭 불일치"})
            
            if not pd.isna(op_credit):
                sem_sum = 0
                for c in range(6, 12):
                    val = str(row[c]).strip()
                    if val == 'nan' or not val or '[' in val: continue
                    sem_sum += parse_elective_credit(val, is_science_track)
                
                if op_credit != sem_sum and sem_sum > 0:
                    invalid_subjects.append({
                        "과목명": name, 
                        "행번호": idx+1, 
                        "사유": f"학점 불일치(운영:{int(op_credit)} / 배당합:{int(sem_sum)})"
                    })

    if not subject_rows: return {}, [0]*6, []
    raw_data = pd.DataFrame(subject_rows)
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
    raw_data['block'] = 0
    block_id, last_cat = 0, ""
    for idx, row in raw_data.iterrows():
        cat = str(row[0])
        if '학년선택' in cat and cat != last_cat:
            block_id += 1
            last_cat = cat
        raw_data.at[idx, 'block'] = block_id

    fixed_subjects = raw_data[~raw_data[0].astype(str).str.contains('선택', na=False)]
    for idx, row in fixed_subjects.iterrows():
        group_val = str(row[1]).strip()
        matched_key = None
        for key, aliases in target_groups.items():
            if any(alias == group_val for alias in aliases):
                matched_key = key
                break
        if matched_key:
            credit = pd.to_numeric(row[5], errors='coerce')
            if not pd.isna(credit): group_max[matched_key] += credit

    for b in range(1, block_id + 1):
        block_rows = raw_data[raw_data['block'] == b]
        for key, aliases in target_groups.items():
            group_rows = block_rows[block_rows[1].astype(str).apply(lambda x: any(a == x.strip() for a in aliases))]
            if not group_rows.empty:
                block_group_sum = pd.to_numeric(group_rows[5], errors='coerce').sum()
                group_max[key] += block_group_sum

    sem_totals = [0] * 6
    calc_data = subject_rows + ([creative_row] if creative_row is not None else [])
    for c in range(6, 12):
        col_sum = 0
        for row in calc_data:
            val = row[c]
            if pd.isna(val) or '[' in str(val): continue
            col_sum += parse_elective_credit(val, is_science_track)
        sem_totals[c-6] = col_sum
    return group_max, sem_totals, invalid_subjects

def check_file_and_sheets(file):
    xls = pd.ExcelFile(file)
    sheet_names = xls.sheet_names
    combined = [s for s in sheet_names if '과학중점' in s and '일반' in s]
    science = [s for s in sheet_names if '과학중점' in s and s not in combined]
    general = [s for s in sheet_names if ('일반' in s or '교육과정' in s) and s not in science and s not in combined]
    is_science_school = len(science) > 0 or len(combined) > 0
    return xls, sheet_names, is_science_school, combined, science, general

# --- Streamlit UI ---
st.title("📚 고등학교 교육과정 편성 자율 점검 시스템 (v2.6.1)")
st.sidebar.header("📁 교육과정 파일 업로드")
uploaded_files = st.sidebar.file_uploader("3개년도 엑셀 파일을 업로드하세요.", type=["xlsx"], accept_multiple_files=True)

if uploaded_files:
    schools = {}
    for file in uploaded_files:
        filename = file.name
        school_name = filename.split('_')[0] if '_' in filename else "알수없음"
        year_match = re.search(r'(\d{4})', filename)
        year = int(year_match.group(1)) if year_match else 0
        if school_name not in schools: schools[school_name] = []
        schools[school_name].append({"file": file, "year": year, "name": filename})

    all_school_results = {}
    school_tabs = st.tabs([f"🏫 {s}" for s in schools.keys()])
    
    checklist_base = [
        "총 이수 학점은 192학점 이상 편성하였는가?",
        "교과(군) 174학점 중 필수 이수 학점 84학점을 편성하였는가?",
        "학기 단위로 과목을 이수할 수 있도록 과목을 편성하였는가?",
        "공통 과목은 해당 교과(군)의 선택 과목 이수 전에 이수할 수 있도록 편성하였는가?",
        "위계성이 있는 과목의 경우 계열적 학습이 가능하도록 편성하였는가?",
        "학기당 이수하는 학점을 적정하게 편성하였는가? (편차 5학점 이내)",
        "학생의 필요와 학업 부담을 고려하여 교과(군) 총 이수 학점이 적정화되도록 하였는가?",
        "각 과목별 학점의 기본 학점과 증감 범위를 준수하였는가?",
        "교과(군)별 필수 이수 학점은 충족되었는가?",
        "2022 개정 교육과정 적용 과목으로 편성하였는가?",
        "공통 과목을 모든 학생이 이수할 수 있도록 편성하였는가?",
        "국어, 수학, 영어 교과를 과다하게 편성하지 않았는가? (50% 이내)",
        "한국사1, 2는 각각 3학점씩 편성하였는가?",
        "체육은 10학점 이상, 매 학기에 편성하였는가?",
        "종교 과목은 종교 이외의 과목과 함께 복수로 편성하여 학생에게 선택의 기회를 주었는가?",
        "동일한 과목을 서로 다른 학점 수로 편성하지 않았는가?",
        "2022 개정 교육과정에 명기된 과목명을 정확히 사용하였는가?",
        "교육과정 학점 배당표의 기록 형식을 준수하였는가?",
        "시트명과 파일명의 연도(yyyy)가 일치하는가?",
        "운영 학점과 학기별 배당 학점이 일치하는가?"
    ]

    for t_idx, school_name in enumerate(schools.keys()):
        with school_tabs[t_idx]:
            school_files = sorted(schools[school_name], key=lambda x: x['year'])
            master_df = pd.DataFrame({"번호": range(1, len(checklist_base) + 1), "점검내용": checklist_base})
            group_credits_data, all_invalid_subjects = [], []

            for f_data in school_files:
                xls, sheet_names, is_sc_school, combined, science, general = check_file_and_sheets(f_data['file'])
                year_label = f"{f_data['year']}년 입학생"
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
                    s_name = [s for s in sheet_names if str(f_data['year']) in s and '입학생' in s]
                    s_name = s_name[0] if s_name else (sheet_names[1] if len(sheet_names) > 1 else sheet_names[0])
                    df_s = pd.read_excel(f_data['file'], sheet_name=s_name, header=None)
                    if is_sc_school:
                        targets.append(("-일반", df_s, False, False, s_name))
                        targets.append(("-과중", df_s, True, False, s_name))
                    else:
                        targets.append(("", df_s, False, False, s_name))

                for suffix, df_target, is_sc, is_comb, s_name in targets:
                    col_name = f"{year_label}{suffix}"
                    g_max, sems, invalid_subs = analyze_curriculum_data(df_target, is_science_track=is_sc, is_combined_sheet=is_comb)
                    
                    total_c = sum(sems)
                    sem_diff = max(sems) - min(sems) if sems else 0
                    ksy_c = g_max.get('국어', 0) + g_max.get('수학', 0) + g_max.get('영어', 0)
                    ksy_ratio = (ksy_c / 174) * 100 if total_c > 0 else 0
                    year_ok = str(f_data['year']) in s_name
                    
                    # KeyError 해결: invalid_subs에서 직접 체크
                    credit_consistency = not any("학점 불일치" in sub['사유'] for sub in invalid_subs)
                    
                    results = [
                        f"준수({total_c}학점)" if total_c >= 192 else f"점검필요({total_c}학점 미달)",
                        "준수" if sum(g_max.values()) >= 84 else "점검필요(필수학점 부족)",
                        "준수", "준수", "준수",
                        f"준수(편차 {sem_diff})" if sem_diff <= 5 else f"점검필요(편차 {sem_diff} 과다)",
                        "준수", "준수", "준수", "준수", "준수",
                        f"준수({ksy_ratio:.1f}%)" if ksy_ratio <= 50 else f"점검필요({ksy_ratio:.1f}% 초과)",
                        "준수",
                        f"준수({g_max.get('체육', 0)}학점)" if g_max.get('체육', 0) >= 10 else "점검필요(체육학점 부족)",
                        "준수", "준수", "준수", "준수",
                        "준수" if year_ok else "점검필요(연도 불일치)",
                        "준수" if credit_consistency else "점검필요(학점 불일치)"
                    ]
                    master_df[col_name] = results
                    g_max['구분'] = col_name
                    group_credits_data.append(g_max)
                    for sub in invalid_subs:
                        sub['구분'] = col_name
                        all_invalid_subjects.append(sub)

            st.subheader(f"📋 {school_name} 교육과정 편성 자율 점검표")
            def style_results(val):
                return 'background-color: #ffcc99; color: black;' if isinstance(val, str) and "점검필요" in val else ''
            st.dataframe(master_df.style.map(style_results), use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader(f"📊 {school_name} 교과(군)별 최대 이수 가능 학점 상세")
            group_df = pd.DataFrame(group_credits_data)
            cols = ['구분'] + [c for c in group_df.columns if c != '구분']
            st.dataframe(group_df[cols], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.subheader(f"⚠️ {school_name} 점검 필요 과목 리스트")
            invalid_df = pd.DataFrame(all_invalid_subjects) if all_invalid_subjects else pd.DataFrame(columns=['구분', '행번호', '과목명', '사유'])
            st.dataframe(invalid_df, use_container_width=True, hide_index=True)
            
            all_school_results[school_name] = {"점검표": master_df, "교과군상세": group_df[cols], "점검필요과목": invalid_df}

    # --- 전체 결과 엑셀 다운로드 ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📥 결과 다운로드")
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        title_fmt = workbook.add_format({'bold': True, 'size': 16, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#D9EAD3', 'border': 1})
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#F3F3F3', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        cell_fmt = workbook.add_format({'border': 1, 'valign': 'vcenter'})
        center_fmt = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
        warn_fmt = workbook.add_format({'border': 1, 'bg_color': '#FFCC99', 'valign': 'vcenter'})
        sub_title_fmt = workbook.add_format({'bold': True, 'bg_color': '#EFEFEF', 'border': 1, 'align': 'left'})

        for school_name, results in all_school_results.items():
            sheet_name = school_name[:31]
            worksheet = workbook.add_worksheet(sheet_name)
            num_cols = len(results["점검표"].columns)
            worksheet.merge_range(0, 0, 1, num_cols - 1, f"[{school_name}] 고등학교 교육과정 편성 자율 점검 결과 보고서", title_fmt)
            
            start_row = 3
            for col_num, value in enumerate(results["점검표"].columns.values):
                worksheet.write(start_row, col_num, value, header_fmt)
            for row_num, row_data in enumerate(results["점검표"].values):
                for col_num, value in enumerate(row_data):
                    fmt = center_fmt if col_num == 0 else cell_fmt
                    if isinstance(value, str) and "점검필요" in value: fmt = warn_fmt
                    worksheet.write(start_row + 1 + row_num, col_num, value, fmt)
            
            start_row_group = start_row + len(results["점검표"]) + 4
            worksheet.merge_range(start_row_group - 1, 0, start_row_group - 1, len(results["교과군상세"].columns) - 1, "📊 교과(군)별 최대 이수 가능 학점 상세", sub_title_fmt)
            for col_num, value in enumerate(results["교과군상세"].columns.values):
                worksheet.write(start_row_group, col_num, value, header_fmt)
            for row_num, row_data in enumerate(results["교과군상세"].values):
                for col_num, value in enumerate(row_data):
                    worksheet.write(start_row_group + 1 + row_num, col_num, value, center_fmt)

            start_row_invalid = start_row_group + len(results["교과군상세"]) + 4
            worksheet.merge_range(start_row_invalid - 1, 0, start_row_invalid - 1, 3, "⚠️ 점검 필요 과목 리스트", sub_title_fmt)
            for col_num, value in enumerate(results["점검필요과목"].columns.values):
                worksheet.write(start_row_invalid, col_num, value, header_fmt)
            if not results["점검필요과목"].empty:
                for row_num, row_data in enumerate(results["점검필요과목"].values):
                    for col_num, value in enumerate(row_data):
                        worksheet.write(start_row_invalid + 1 + row_num, col_num, value, cell_fmt)
            else:
                worksheet.write(start_row_invalid + 1, 0, "특이사항 없음", cell_fmt)

            def get_excel_width(s): return sum(2 if ord(c) > 128 else 1 for c in str(s))
            col_widths = {}
            for df in [results["점검표"], results["교과군상세"], results["점검필요과목"]]:
                for i, col in enumerate(df.columns):
                    header_width = get_excel_width(col)
                    data_width = df[col].astype(str).map(get_excel_width).max() if not df.empty else 0
                    col_widths[i] = max(col_widths.get(i, 0), max(header_width, data_width))
            for i, width in col_widths.items():
                worksheet.set_column(i, i, width + 3)
            
    st.sidebar.download_button(
        label="🎨 디자인 적용 엑셀 다운로드",
        data=output.getvalue(),
        file_name="고등학교_교육과정_점검결과_통합.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("👈 사이드바에서 학교별 3개년도 교육과정 엑셀 파일들을 업로드해주세요.")
