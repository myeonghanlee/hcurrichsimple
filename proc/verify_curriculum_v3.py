import pandas as pd
import re

def extract_ksy_max_credits(df):
    """
    규칙 1: 국어, 수학, 영어 교과의 최대 이수 가능 학점 계산
    """
    # 과목 영역 (보통 7행 ~ 117행)
    raw_data = df.iloc[6:117].copy() 
    raw_data.columns = range(df.shape[1])
    raw_data[1] = raw_data[1].ffill() 
    
    ksy_max = {'국 어': 0, '수 학': 0, '영 어': 0}
    
    for idx, row in raw_data.iterrows():
        group = str(row[1]).strip()
        if group in ksy_max:
            has_value = False
            for c in range(6, 12):
                val = str(row[c]).strip()
                if val != 'nan' and val:
                    has_value = True
                    break
            
            if has_value:
                # 규칙 1-1 & 1-2: F열의 운영학점을 합산
                credit = pd.to_numeric(row[5], errors='coerce')
                if not pd.isna(credit):
                    ksy_max[group] += credit
    return ksy_max

def calculate_semester_credits(df):
    """
    규칙 2: 학기별 이수 학점 계산
    """
    # 과목 영역(7~117) + 창체(119)만 포함
    # 합계 행(118, 120+)은 제외
    subject_data = df.iloc[6:117]
    creative_data = df.iloc[118:119] # 119행 (0-indexed 118)
    
    raw_data = pd.concat([subject_data, creative_data])
    raw_data.columns = range(df.shape[1])
    
    sem_totals = [0] * 6
    for c in range(6, 12):
        col_sum = 0
        for val in raw_data[c]:
            s_val = str(val).strip()
            if s_val == 'nan' or not s_val:
                continue
            
            # 규칙 2-2: [n] 제외
            if '[' in s_val and ']' in s_val:
                continue
            
            # 규칙 2-3: xx(택n)일 경우 xx를 더함
            if '(' in s_val and '택' in s_val:
                match = re.match(r'^(\d+)', s_val)
                if match:
                    col_sum += int(match.group(1))
            else:
                # 일반 숫자
                match = re.search(r'(\d+)', s_val)
                if match:
                    col_sum += int(match.group(1))
        sem_totals[c-6] = col_sum
    return sem_totals

def main(file_path):
    print(f"--- 교육과정 분석 보고서 ({file_path.split('/')[-1]}) ---")
    all_sheets = pd.read_excel(file_path, sheet_name=None, header=None)
    
    target_sheet = '2025입학생' if '2025입학생' in all_sheets else '2026입학생'
    sheet_df = all_sheets[target_sheet]
    
    ksy = extract_ksy_max_credits(sheet_df)
    sems = calculate_semester_credits(sheet_df)
    
    print("\n1. 국어, 수학, 영어 과목의 최대 이수 가능 학점")
    for k, v in ksy.items():
        print(f" - {k}: {int(v)}학점")
        
    print("\n2. 학기별 이수학점")
    sem_names = ['1-1', '1-2', '2-1', '2-2', '3-1', '3-2']
    for name, val in zip(sem_names, sems):
        print(f" - {name}학기: {int(val)}학점")

if __name__ == "__main__":
    main('/home/ubuntu/upload/강서고_2027학년도입학생교육과정학점배당표.xlsx')
    print("\n" + "="*40 + "\n")
    main('/home/ubuntu/upload/동양고_2027학년도입학생교육과정학점배당표.xlsx')
