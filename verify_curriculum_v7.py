import pandas as pd
import re

def parse_elective_credit(val, is_science_track=False):
    """
    규칙 1-3-1: kk~ll(택n) 처리
    일반 학생은 kk(작은 수), 과학중점 학생은 ll(큰 수) 반환
    """
    # 줄바꿈 및 공백 제거하여 연속된 숫자로 만듦
    s_val = re.sub(r'\s+', '', str(val))
    if '택' in s_val and '~' in s_val:
        # \d+~\d+ 패턴 추출
        match = re.search(r'(\d+)~(\d+)', s_val)
        if match:
            kk = int(match.group(1))
            ll = int(match.group(2))
            return ll if is_science_track else kk
    
    # 기존 xx(택n) 처리
    if '택' in s_val:
        match = re.match(r'^(\d+)', s_val)
        if match: return int(match.group(1))
    
    # 일반 숫자
    match = re.search(r'(\d+)', s_val)
    if match: return int(match.group(1))
    
    return 0

def analyze_sheet(df, is_science_track=False, is_combined_sheet=False):
    """
    단일 시트에 대한 분석 수행
    is_science_track: 과학중점 과정으로 분석할지 여부
    is_combined_sheet: 통합 시트 여부 (과중-지정 필터링 적용)
    """
    raw_data = df.iloc[6:117].copy()
    raw_data.columns = range(df.shape[1])
    raw_data[0] = raw_data[0].ffill() # 구분
    raw_data[1] = raw_data[1].ffill() # 교과군
    
    # 통합 시트일 경우 '과중 - 지정' 필터링 (규칙 1-1, 1-2)
    if is_combined_sheet:
        # M열(index 12) 확인
        if is_science_track:
            # 과학중점 학생은 모든 행 포함 (과중-지정 포함)
            pass 
        else:
            # 일반 학생은 '과중 - 지정' 행 제외
            raw_data = raw_data[~raw_data[12].astype(str).str.contains('과중 - 지정', na=False)]

    # 교과군별 최대 학점 계산 (기존 로직 유지하되 parse_elective_credit 적용)
    target_groups = {
        '국어': ['국 어'], '수학': ['수 학'], '영어': ['영 어'],
        '사회': ['사 회\n(역사/도덕 포함)', '사회'], '과학': ['과 학'],
        '체육': ['체 육'], '기가/정보': ['기술∙가정/정보', '기술·가정/정보'], '교양': ['교 양']
    }
    
    group_max = {k: 0 for k in target_groups.keys()}
    sem_totals = [0] * 6
    
    # 선택 블록 전파 로직
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

    # 학점 집계
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

    # 학기별 합계 (창체 포함)
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

def main(file_path):
    print(f"\n=== 파일 분석: {file_path.split('/')[-1]} ===")
    xls = pd.ExcelFile(file_path)
    sheet_names = xls.sheet_names
    
    # 시트 구성 파악
    combined_sheets = [s for s in sheet_names if '과학중점' in s and '일반' in s]
    science_sheets = [s for s in sheet_names if '과학중점' in s and s not in combined_sheets]
    general_sheets = [s for s in sheet_names if ('일반' in s or '교육과정' in s) and s not in science_sheets and s not in combined_sheets]
    
    if combined_sheets:
        s_name = combined_sheets[0]
        df = pd.read_excel(file_path, sheet_name=s_name, header=None)
        print(f"시트 유형: 통합 시트 ({s_name})")
        
        print("\n[과학중점과정 학생 분석]")
        g_max, sems = analyze_sheet(df, is_science_track=True, is_combined_sheet=True)
        print(f" - 수학: {g_max['수학']}학점, 과학: {g_max['과학']}학점")
        print(f" - 학기별 합계: {sems}")
        
        print("\n[일반과정 학생 분석]")
        g_max, sems = analyze_sheet(df, is_science_track=False, is_combined_sheet=True)
        print(f" - 수학: {g_max['수학']}학점, 과학: {g_max['과학']}학점")
        print(f" - 학기별 합계: {sems}")
        
    elif science_sheets and general_sheets:
        print("시트 유형: 분리 시트")
        for s_name in science_sheets:
            print(f"\n[{s_name} 분석 - 과학중점 기준]")
            df = pd.read_excel(file_path, sheet_name=s_name, header=None)
            g_max, sems = analyze_sheet(df, is_science_track=True, is_combined_sheet=False)
            print(f" - 수학: {g_max['수학']}학점, 과학: {g_max['과학']}학점")
            print(f" - 학기별 합계: {sems}")
            
        for s_name in general_sheets:
            print(f"\n[{s_name} 분석 - 일반 기준]")
            df = pd.read_excel(file_path, sheet_name=s_name, header=None)
            g_max, sems = analyze_sheet(df, is_science_track=False, is_combined_sheet=False)
            print(f" - 수학: {g_max['수학']}학점, 과학: {g_max['과학']}학점")
            print(f" - 학기별 합계: {sems}")
    else:
        # 기본 처리
        s_name = sheet_names[1] if len(sheet_names) > 1 else sheet_names[0]
        print(f"시트 유형: 기본 시트 ({s_name})")
        df = pd.read_excel(file_path, sheet_name=s_name, header=None)
        g_max, sems = analyze_sheet(df)
        print(f" - 수학: {g_max['수학']}학점, 과학: {g_max['과학']}학점")
        print(f" - 학기별 합계: {sems}")

if __name__ == "__main__":
    # 명덕고와 마포고 테스트
    main('/home/ubuntu/upload/명덕고_2027학년도입학생교육과정학점배당표.xlsx')
    main('/home/ubuntu/upload/마포고_2027학년도입학생교육과정학점배당표.xlsx')
