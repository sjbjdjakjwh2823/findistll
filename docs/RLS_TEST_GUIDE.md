# RLS Test Guide (Preciso)

## 목적
- JWT tenant_id 기반 RLS 정책이 교차 테넌트 접근을 차단하는지 확인

## 절차
1. Supabase JWT에 tenant_id 클레임 포함
2. tenant A로 데이터 생성
3. tenant B로 접근 시 0건 반환 확인

## 적용 SQL
- `scripts/apply_rls.sql`
