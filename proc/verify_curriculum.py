import pandas as pd
import openpyxl
import re

# 1. 고시 과목 데이터 정의 (지침 기반)
OFFICIAL_SUBJECTS = {
    "국어": ["공통국어1", "공통국어2", "화법과 언어", "독서와 작문", "문학", "주제 탐구 독서", "문학과 영상", "직무 의사소통", "독서 토론과 글쓰기", "매체 의사소통", "언어생활 탐구"],
    "수학": ["공통수학1", "공통수학2", "기본수학1", "기본수학2", "대수", "미적분Ⅰ", "확률과 통계", "기하", "미적분Ⅱ", "경제 수학", "인공지능 수학", "직무 수학", "수학과 문화", "실용 통계", "수학과제 탐구"],
    "영어": ["공통영어1", "공통영어2", "기본영어1", "기본영어2", "영어Ⅰ", "영어Ⅱ", "영어 독해와 작문", "영미 문학 읽기", "영어 발표와 토론", "심화 영어", "심화 영어 독해와 작문", "직무 영어", "실생활 영어 회화", "미디어 영어", "세계 문화와 영어"],
    "사회": ["한국사1", "한국사2", "통합사회1", "통합사회2", "세계시민과 지리", "세계사", "사회와 문화", "현대사회와 윤리", "한국지리 탐구", "도시의 미래 탐구", "동아시아 역사 기행", "정치", "법과 사회", "경제", "윤리와 사상", "인문학과 윤리", "국제 관계의 이해", "여행지리", "역사로 탐구하는 현대 세계", "사회문제 탐구", "금융과 경제생활", "윤리문제 탐구", "기후변화와 지속가능한 세계"],
    "과학": ["통합과학1", "통합과학2", "과학탐구실험1", "과학탐구실험2", "물리학", "화학", "생명과학", "지구과학", "역학과 에너지", "전자기와 양자", "물질과 에너지", "화학 반응의 세계", "세포와 물질대사", "생물의 유전", "지구시스템과학", "행성우주과학", "과학의 역사와 문화", "기후변화와 환경생태", "융합과학 탐구"],
    "체육": ["체육1", "체육2", "운동과 건강", "스포츠 문화", "스포츠 과학", "스포츠 생활1", "스포츠 생활2"],
    "예술": ["음악", "미술", "연극", "음악 연주와 창작", "음악 감상과 비평", "미술 창작", "미술 감상과 비평", "음악과 미디어", "미술과 매체"],
    "기술∙가정/정보": ["기술∙가정", "정보", "로봇과 공학세계", "생활과학 탐구", "창의 공학 설계", "지식 재산 일반", "생애 설계와 자립", "아동발달과 보모", "인공지능 기초", "데이터 과학", "소프트웨어와 생활"]
}

ALL_OFFICIAL_NAMES = [sub for list in OFFICIAL_SUBJECTS.values() for sub in list]

def verify_curriculum(file_path):
    print(f"--- 검증 시작: {file_path} ---")
    
    # 엑셀 로드
    df = pd.read_excel(file_path, sheet_name='2026입학생', header=None)
    
    # 데이터 영역 추출 (7행부터 107행까지, B~F열 기준)
    data = df.iloc[6:107, 1:6] # B:F columns
    data.columns = ['교과군', '유형', '과목명', '기본학점', '운영학점']
    
    # 1. 과목명 일치 여부 점검
    print("\n[1] 과목명 일치 여부 점검")
    errors = []
    for idx, row in data.iterrows():
        name = str(row['과목명']).strip()
        if name == 'nan' or not name: continue
        
        # 타시도 승인과목은 제외해야 하지만, 여기서는 고시 과목 위주로 체크
        if name not in ALL_OFFICIAL_NAMES:
            errors.append(f"행 {idx+1}: '{name}' (고시 과목명과 불일치)")
    
    if errors:
        for e in errors: print(f" - {e}")
    else:
        print(" - 모든 과목명이 고시 명칭과 일치합니다.")

    # 2. 총 이수 학점 점검
    print("\n[2] 총 이수 학점 점검")
    total_credits = pd.to_numeric(data['운영학점'], errors='coerce').sum()
    # 실제 파일에서는 창체 18학점이 별도로 있을 것이나, 여기서는 교과만 합산
    print(f" - 교과 이수 학점 합계: {total_credits}학점 (지침: 174학점 이상)")
    
    # 3. 국수영 비중 점검 (50% 이내)
    print("\n[3] 국어/수학/영어 비중 점검")
    ksy_groups = ['국 어', '수 학', '영 어']
    ksy_credits = pd.to_numeric(data[data['교과군'].isin(ksy_groups)]['운영학점'], errors='coerce').sum()
    ratio = (ksy_credits / total_credits) * 100 if total_credits > 0 else 0
    print(f" - 국수영 합계: {ksy_credits}학점 (비중: {ratio:.2f}%)")
    if ratio > 50:
        print(" !!! 경고: 국수영 비중이 50%를 초과했습니다.")
    else:
        print(" - 국수영 비중 지침을 준수합니다.")

    # 4. 한국사 학점 점검
    print("\n[4] 한국사 학점 점검")
    history = data[data['과목명'].str.contains('한국사', na=False)]
    for _, row in history.iterrows():
        if row['운영학점'] != 3:
            print(f" !!! 경고: {row['과목명']}의 운영학점이 {row['운영학점']}입니다. (지침: 3학점)")

    # 5. 학기별 편차 점검 (G~L열 데이터 필요)
    print("\n[5] 학기별 이수 학점 편차 점검")
    semester_data = df.iloc[6:107, 6:12] # G:L columns
    sem_sums = semester_data.apply(pd.to_numeric, errors='coerce').sum()
    max_sem = sem_sums.max()
    min_sem = sem_sums.min()
    diff = max_sem - min_sem
    print(f" - 학기별 학점 합계: {list(sem_sums)}")
    print(f" - 최대/최소 차이: {diff}학점")
    if diff > 5:
        print(" !!! 경고: 학기 간 학점 차이가 5학점을 초과했습니다.")

if __name__ == "__main__":
    verify_curriculum('/home/ubuntu/upload/동양고_2027학년도입학생교육과정학점배당표.xlsx')
