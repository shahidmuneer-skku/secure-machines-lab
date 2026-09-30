/**
 * Legal texts (EN + KO). Structure follows Korean requirements (Electronic Commerce Act, PIPA).
 * Company details come from lib/company.ts (placeholders until the owner fills them in).
 * The owner should have counsel review these before launch.
 */
import { COMPANY } from "@/lib/company"

export interface LegalSection {
  heading: string
  body: string[]
}

export interface LegalDoc {
  title: string
  intro: string
  sections: LegalSection[]
}

type Locale = "en" | "ko"

const retentionEn = "Uploaded files and results are deleted automatically after the retention period of your plan: guest trial 1 day, free accounts 7 days, Basic 14 days, Pro 30 days, Business 90 days (administrators may configure other periods for enterprise agreements). Job metadata needed for billing records is kept as required by law."
const retentionKo = "업로드한 파일과 분석 결과는 요금제별 보관 기간이 지나면 자동 삭제됩니다: 비회원 체험 1일, 무료 회원 7일, 베이직 14일, 프로 30일, 비즈니스 90일(기업 계약 시 별도 설정 가능). 결제 기록에 필요한 작업 메타데이터는 관계 법령에 따라 보관합니다."

export const TERMS: Record<Locale, LegalDoc> = {
  en: {
    title: "Terms of Service",
    intro: `These Terms govern your use of the Secure Machines Lab platform (the "Service") operated by ${COMPANY.name} (the "Company"). Effective ${COMPANY.effectiveDate}.`,
    sections: [
      { heading: "1. Purpose", body: ["These Terms set out the rights, obligations and responsibilities of the Company and users regarding the Service, which detects deepfakes and AI-generated images and videos, scans long-form video, verifies multimedia news, and provides related reports and APIs."] },
      { heading: "2. Definitions", body: [
        "“User” means anyone who uses the Service, including guests using the free trial and registered members.",
        "“Credits” means the prepaid units used to pay for analyses. Credits have no cash value.",
        "“Job” means one analysis request for one file or news case. “API key” means a credential for programmatic access.",
      ] },
      { heading: "3. The Service and its limits", body: [
        "Detection results are probabilistic estimates produced by machine-learning models and may be wrong (false positives and false negatives). Results support, but do not replace, expert judgement.",
        "Results, reports and explanations must not be used as sole legal evidence. Accuracy measured on research datasets does not guarantee accuracy on every file.",
      ] },
      { heading: "4. Accounts and security", body: [
        "You must provide a valid email address and keep your password, authenticator devices and API keys confidential. You are responsible for activity under your account and keys.",
        "Staff accounts must use two-factor authentication. We may require additional verification to protect accounts.",
      ] },
      { heading: "5. Using the Service and credits", body: [
        "The credit cost of each analysis is shown before you submit it. Credits are reserved when a job is created and charged only when at least one model produces a result; failed analyses, cancellations and files with no detectable face for face-only analyses are not charged.",
        "Free credits (daily and welcome bonus) and paid credits are used in order of soonest expiry.",
      ] },
      { heading: "6. Your obligations and prohibited content", body: [
        "You warrant that you have the rights and any required consents for the content you upload, including consent of identifiable people where required by law.",
        "You must not upload child sexual abuse material, non-consensual intimate imagery, content that infringes others’ rights, or use the Service to harass, defame or deceive. You must not probe, overload or reverse-engineer the Service or share API keys publicly.",
        "We may remove prohibited content and suspend accounts that violate these Terms.",
      ] },
      { heading: "7. Intellectual property and data use", body: [
        "You keep all rights to your content. You grant us only the limited licence needed to process it and provide the Service.",
        "We use your uploads to improve our models only if you opt in under Settings → Privacy. You can withdraw that consent at any time.",
        "The Service, models, software and reports templates are the Company’s property.",
      ] },
      { heading: "8. Data retention", body: [retentionEn] },
      { heading: "9. Paid services and credits", body: [
        "Credit packs are one-time purchases. Subscriptions renew monthly until cancelled and grant a monthly credit allowance.",
        "Validity: daily free credits until the end of the day (KST); welcome bonus 30 days; subscription credits until the end of the billing period; purchased credits 12 months unless stated otherwise at purchase.",
        "Credits cannot be transferred, resold or exchanged for cash, except as required by the Refund Policy or law.",
      ] },
      { heading: "10. Payments and receipts", body: [
        "KRW payments are processed by Toss Payments; USD payments by Stripe. We never receive or store full card numbers. Receipts are available under Credits & billing.",
      ] },
      { heading: "11. Cancellation and refunds", body: ["Cancellations and refunds are governed by our Refund Policy and the Act on the Consumer Protection in Electronic Commerce."] },
      { heading: "12. API", body: ["API keys are subject to scopes, rate limits and optional IP allowlists. API usage consumes credits exactly like the web application. We may revoke keys that are leaked or abused."] },
      { heading: "13. Suspension and discontinuation", body: [
        "We may suspend the Service temporarily for maintenance, security or failures. We will give at least 30 days’ notice before discontinuing the Service.",
        "If the Service is discontinued, unused paid credits are refunded in the original currency; unused subscription periods are refunded pro-rata. Free and bonus credits are not refunded. Credits are forfeited if an account is suspended for violating these Terms.",
      ] },
      { heading: "14. Limitation of liability", body: ["To the extent permitted by law, the Company is not liable for decisions made based on detection results or for damages caused by third parties, except in cases of wilful misconduct or gross negligence."] },
      { heading: "15. Changes to these Terms", body: ["We will announce changes at least 7 days in advance (30 days for changes unfavourable to users) on the website or by email. If you do not agree, you may close your account."] },
      { heading: "16. Governing law and jurisdiction", body: ["These Terms are governed by the laws of the Republic of Korea. Disputes are subject to the courts having jurisdiction under the Civil Procedure Act. If the Korean and English versions differ, the Korean version prevails."] },
      { heading: "17. Business information", body: [`${COMPANY.name} · CEO ${COMPANY.representative} · Business registration ${COMPANY.businessRegistrationNo} · Mail-order ${COMPANY.mailOrderRegistrationNo} · ${COMPANY.address} · ${COMPANY.supportEmail}`] },
    ],
  },
  ko: {
    title: "서비스 이용약관",
    intro: `본 약관은 ${COMPANY.name}(이하 “회사”)가 운영하는 Secure Machines Lab 플랫폼(이하 “서비스”)의 이용에 관한 사항을 규정합니다. 시행일: ${COMPANY.effectiveDate}.`,
    sections: [
      { heading: "제1조 (목적)", body: ["본 약관은 딥페이크 및 AI 생성 이미지·영상 탐지, 장편 영상 분석, 멀티미디어 뉴스 검증과 관련 보고서 및 API를 제공하는 서비스의 이용과 관련하여 회사와 이용자의 권리, 의무 및 책임사항을 규정함을 목적으로 합니다."] },
      { heading: "제2조 (정의)", body: [
        "“이용자”란 무료 체험을 이용하는 비회원과 회원을 포함하여 서비스를 이용하는 모든 자를 말합니다.",
        "“크레딧”이란 분석 이용료를 결제하기 위한 선불 단위이며 현금 가치가 없습니다.",
        "“작업”이란 파일 1개 또는 뉴스 사례 1건에 대한 분석 요청을, “API 키”란 프로그램 방식 접근을 위한 인증 수단을 말합니다.",
      ] },
      { heading: "제3조 (서비스의 내용과 한계)", body: [
        "탐지 결과는 머신러닝 모델이 산출한 확률적 추정치로서 오탐 또는 미탐이 발생할 수 있으며, 전문가의 판단을 보조할 뿐 대체하지 않습니다.",
        "결과, 보고서 및 설명은 단독 법적 증거로 사용될 수 없으며, 연구 데이터셋에서 측정된 정확도가 모든 파일에 대한 정확도를 보장하지 않습니다.",
      ] },
      { heading: "제4조 (계정 및 보안)", body: [
        "이용자는 유효한 이메일을 제공하고 비밀번호, 인증 기기 및 API 키를 안전하게 관리하여야 하며, 계정과 키에서 발생한 행위에 대한 책임을 집니다.",
        "관리자 계정은 2단계 인증을 사용해야 하며, 회사는 계정 보호를 위해 추가 인증을 요구할 수 있습니다.",
      ] },
      { heading: "제5조 (서비스 이용 및 크레딧 차감)", body: [
        "각 분석의 크레딧 비용은 요청 전에 표시됩니다. 크레딧은 작업 생성 시 예약되며, 하나 이상의 모델이 결과를 산출한 경우에만 차감됩니다. 분석 실패, 취소, 얼굴 기반 분석에서 얼굴이 검출되지 않은 경우에는 차감되지 않습니다.",
        "무료 크레딧(일일 및 가입 보너스)과 유료 크레딧은 만료일이 빠른 순서로 사용됩니다.",
      ] },
      { heading: "제6조 (이용자의 의무 및 금지 콘텐츠)", body: [
        "이용자는 업로드하는 콘텐츠에 대한 권리와 법령상 필요한 동의(식별 가능한 인물의 동의 등)를 보유하고 있음을 보증합니다.",
        "아동·청소년 성착취물, 비동의 촬영물, 타인의 권리를 침해하는 콘텐츠를 업로드하거나 서비스를 괴롭힘·명예훼손·기만에 이용하여서는 안 되며, 서비스를 역설계·과부하시키거나 API 키를 공개해서는 안 됩니다.",
        "회사는 금지 콘텐츠를 삭제하고 약관을 위반한 계정의 이용을 제한할 수 있습니다.",
      ] },
      { heading: "제7조 (지식재산권 및 데이터 이용)", body: [
        "이용자는 콘텐츠에 대한 모든 권리를 보유하며, 회사에 서비스 제공에 필요한 범위의 이용만을 허락합니다.",
        "회사는 이용자가 설정 → 개인정보에서 동의한 경우에만 업로드 파일을 모델 개선에 이용하며, 이용자는 언제든지 동의를 철회할 수 있습니다.",
        "서비스, 모델, 소프트웨어 및 보고서 양식에 대한 권리는 회사에 있습니다.",
      ] },
      { heading: "제8조 (데이터 보관)", body: [retentionKo] },
      { heading: "제9조 (유료 서비스 및 크레딧)", body: [
        "크레딧 팩은 1회성 구매이며, 구독은 해지 시까지 매월 갱신되고 월간 크레딧을 제공합니다.",
        "유효기간: 일일 무료 크레딧은 당일(한국시간) 종료 시까지, 가입 보너스는 30일, 구독 크레딧은 해당 결제 기간 종료 시까지, 구매 크레딧은 구매 시 별도 표시가 없는 한 12개월입니다.",
        "크레딧은 환불정책 또는 법령에 따른 경우를 제외하고 양도, 재판매 또는 현금 교환할 수 없습니다.",
      ] },
      { heading: "제10조 (결제 및 영수증)", body: ["원화 결제는 토스페이먼츠, 달러 결제는 Stripe를 통해 처리되며, 회사는 카드번호 전체를 수집하거나 저장하지 않습니다. 영수증은 크레딧 및 결제 메뉴에서 확인할 수 있습니다."] },
      { heading: "제11조 (청약철회 및 환불)", body: ["청약철회 및 환불은 환불정책과 「전자상거래 등에서의 소비자보호에 관한 법률」에 따릅니다."] },
      { heading: "제12조 (API)", body: ["API 키에는 권한 범위, 호출 제한 및 선택적 IP 허용 목록이 적용되며, API 이용 시 웹과 동일하게 크레딧이 차감됩니다. 유출되거나 남용된 키는 회사가 폐기할 수 있습니다."] },
      { heading: "제13조 (서비스 중단)", body: [
        "회사는 점검, 보안 또는 장애 시 서비스를 일시 중단할 수 있으며, 서비스를 종료하는 경우 30일 전에 공지합니다.",
        "서비스 종료 시 미사용 유료 크레딧은 결제 통화로 환불하고, 구독 잔여 기간은 일할 계산하여 환불합니다. 무료 및 보너스 크레딧은 환불되지 않으며, 약관 위반으로 이용이 정지된 경우 크레딧은 소멸합니다.",
      ] },
      { heading: "제14조 (책임의 제한)", body: ["회사는 관계 법령이 허용하는 범위에서 탐지 결과에 근거한 이용자의 판단 및 제3자에 의한 손해에 대하여 고의 또는 중대한 과실이 없는 한 책임을 지지 않습니다."] },
      { heading: "제15조 (약관의 변경)", body: ["회사는 약관 변경 시 최소 7일 전(이용자에게 불리한 변경은 30일 전) 웹사이트 또는 이메일로 공지하며, 이용자는 동의하지 않을 경우 회원 탈퇴할 수 있습니다."] },
      { heading: "제16조 (준거법 및 관할)", body: ["본 약관은 대한민국 법률에 따르며, 분쟁은 민사소송법상 관할 법원에 제기합니다. 국문과 영문이 다를 경우 국문이 우선합니다."] },
      { heading: "제17조 (사업자 정보)", body: [`${COMPANY.name} · 대표 ${COMPANY.representative} · 사업자등록번호 ${COMPANY.businessRegistrationNo} · 통신판매업신고 ${COMPANY.mailOrderRegistrationNo} · ${COMPANY.address} · ${COMPANY.supportEmail}`] },
    ],
  },
}

export const PRIVACY: Record<Locale, LegalDoc> = {
  en: {
    title: "Privacy Policy",
    intro: `${COMPANY.name} processes personal information in accordance with the Personal Information Protection Act of Korea (PIPA). Effective ${COMPANY.effectiveDate}.`,
    sections: [
      { heading: "1. What we collect, why, and for how long", body: [
        "Account: email, password hash (Argon2id), name, language, time zone — to provide the account; kept until you delete it, then removed within 30 days.",
        "Detection service: uploaded images/videos, derived artifacts (heatmaps, face crops), results — to perform analyses; " + retentionEn,
        "Security & API: IP address (sessions, API request logs), device/browser information, audit logs — to secure accounts and prevent abuse; API request logs 30 days, access logs at least 3 months.",
        "Payments: order, amount, payment method type and provider reference (never full card numbers) — to process payments and issue receipts; 5 years as required by the E-Commerce Act.",
        "Guest trial: a random device cookie and a hashed, truncated IP network — to enforce the daily trial limit; 24 hours of usage counters.",
        "AI training (only if you opt in): files you upload after consenting — to train and evaluate detection models; up to 3 years or until you withdraw consent.",
      ] },
      { heading: "2. How we handle uploaded content", body: [
        "Uploads are used only to produce your results (and, with consent, to improve models). They are never used for advertising. Staff access media only when needed for a support request you make or when required by law.",
        "Files are stored under random identifiers in private storage and served only through short-lived, access-checked links.",
      ] },
      { heading: "3. Retention required by law", body: ["Records of contracts and withdrawals: 5 years; payment and supply records: 5 years; consumer complaints and disputes: 3 years (E-Commerce Act); website access logs: 3 months (Protection of Communications Secrets Act)."] },
      { heading: "4. Provision to third parties", body: ["We do not provide personal information to third parties except with your consent, where required by law, or where urgently necessary to protect life or property."] },
      { heading: "5. Processors (entrustment)", body: [
        "Toss Payments Co., Ltd. — KRW payment processing and billing keys.",
        "Stripe, Inc. — USD payment processing, subscriptions and invoices.",
        "[EMAIL PROVIDER] — transactional email (verification, password reset, receipts).",
        "[HOSTING PROVIDER / DATA CENTRE] — infrastructure hosting. Detection models run on the Company’s own servers.",
        "Cloudflare, Inc. — CAPTCHA (Turnstile), only if enabled.",
      ] },
      { heading: "6. Transfers abroad", body: [
        "If you pay in USD, payment data is transferred to Stripe, Inc. (USA) at the time of payment for the purposes above and retained per Stripe’s legal obligations.",
        "If the administrator enables the Claude engine for news verification, case text and media are sent to Anthropic, PBC (USA) for processing at the time of the request. The default engine runs locally and sends nothing abroad.",
        "You may refuse such transfers by not using the corresponding payment method or feature.",
      ] },
      { heading: "7. Destruction", body: ["When a retention period ends we delete electronic files so that they cannot be recovered. Records we must keep by law are stored separately with restricted access."] },
      { heading: "8. Your rights", body: [
        "You can access, correct, delete or restrict processing of your information, and withdraw consent. Settings → Privacy lets you download a data export, toggle AI-training consent and delete your account. You can also email " + COMPANY.privacyEmail + ".",
        "Children under 14 may not register.",
      ] },
      { heading: "9. Cookies", body: ["We use strictly necessary cookies only: session cookie (HttpOnly, sign-in), CSRF token, language preference and the guest-trial device cookie. We do not use advertising or cross-site tracking cookies."] },
      { heading: "10. Security measures", body: ["Encrypted transport (TLS), Argon2id password hashing, two-factor authentication and passkeys, encryption of payment billing keys at rest, role-based access control with audit logging, least-privilege model workers, and regular security updates."] },
      { heading: "11. Privacy officer", body: [`${COMPANY.privacyOfficer} · ${COMPANY.privacyEmail}. We respond without delay.`] },
      { heading: "12. Remedies", body: ["Personal Information Dispute Mediation Committee (1833-6972, kopico.go.kr), Personal Information Infringement Report Center (118, privacy.kisa.or.kr), Supreme Prosecutors’ Office (1301), Korean National Police Agency Cyber Bureau (182)."] },
      { heading: "13. Changes", body: ["We announce changes at least 7 days in advance (30 days for material changes)."] },
    ],
  },
  ko: {
    title: "개인정보처리방침",
    intro: `${COMPANY.name}는 「개인정보 보호법」에 따라 이용자의 개인정보를 처리합니다. 시행일: ${COMPANY.effectiveDate}.`,
    sections: [
      { heading: "1. 처리 목적, 항목 및 보유 기간", body: [
        "회원 관리: 이메일, 비밀번호 해시(Argon2id), 이름, 언어, 시간대 — 계정 제공 목적, 탈퇴 시까지(탈퇴 후 30일 이내 파기).",
        "탐지 서비스: 업로드한 이미지·영상, 파생 산출물(히트맵, 얼굴 이미지), 결과 — 분석 수행 목적. " + retentionKo,
        "보안 및 API: IP 주소(세션, API 요청 로그), 기기·브라우저 정보, 감사 로그 — 계정 보호 및 부정 이용 방지 목적. API 요청 로그 30일, 접속 기록 최소 3개월.",
        "결제: 주문, 금액, 결제수단 종류, 결제대행사 거래번호(카드번호 전체는 수집하지 않음) — 결제 처리 및 영수증 발급 목적, 전자상거래법에 따라 5년.",
        "비회원 체험: 무작위 기기 쿠키, 해시 처리·축약된 IP 대역 — 일일 체험 한도 적용 목적, 이용 횟수 24시간.",
        "AI 학습(동의한 경우에만): 동의 이후 업로드한 파일 — 탐지 모델 학습 및 평가 목적, 최대 3년 또는 동의 철회 시까지.",
      ] },
      { heading: "2. 업로드 콘텐츠 처리 원칙", body: [
        "업로드 파일은 분석 결과 제공(동의 시 모델 개선)에만 이용하며 광고 목적으로 이용하지 않습니다. 이용자의 문의 처리 또는 법령상 필요한 경우를 제외하고 직원이 미디어를 열람하지 않습니다.",
        "파일은 무작위 식별자로 비공개 저장소에 저장되며, 접근 권한이 확인된 단기 링크로만 제공됩니다.",
      ] },
      { heading: "3. 법령에 따른 보관", body: ["계약 또는 청약철회 기록 5년, 대금 결제 및 재화 공급 기록 5년, 소비자 불만 또는 분쟁 처리 기록 3년(전자상거래법), 웹사이트 접속 기록 3개월(통신비밀보호법)."] },
      { heading: "4. 제3자 제공", body: ["이용자의 동의가 있거나 법령에 근거가 있는 경우, 또는 생명·재산 보호를 위해 긴급히 필요한 경우를 제외하고 개인정보를 제3자에게 제공하지 않습니다."] },
      { heading: "5. 처리 위탁", body: [
        "㈜토스페이먼츠 — 원화 결제 처리 및 자동결제 빌링키.",
        "Stripe, Inc. — 달러 결제, 구독 및 인보이스.",
        "[이메일 발송 업체] — 인증, 비밀번호 재설정, 영수증 이메일 발송.",
        "[호스팅 업체 / 데이터센터] — 인프라 운영. 탐지 모델은 회사 자체 서버에서 실행됩니다.",
        "Cloudflare, Inc. — CAPTCHA(Turnstile, 사용 시).",
      ] },
      { heading: "6. 국외 이전", body: [
        "달러로 결제하는 경우 결제 정보가 결제 시점에 Stripe, Inc.(미국)으로 이전되며, Stripe의 법적 의무에 따라 보관됩니다.",
        "관리자가 뉴스 검증에 Claude 엔진을 활성화한 경우, 요청 시점에 사례 내용과 미디어가 Anthropic, PBC(미국)로 전송되어 처리됩니다. 기본 엔진은 국내 서버에서 로컬로 실행되어 국외로 전송하지 않습니다.",
        "이용자는 해당 결제수단 또는 기능을 이용하지 않음으로써 국외 이전을 거부할 수 있습니다.",
      ] },
      { heading: "7. 파기 절차 및 방법", body: ["보유 기간이 끝나면 전자적 파일은 복구할 수 없는 방법으로 삭제하며, 법령에 따라 보관하는 정보는 별도로 분리하여 접근을 제한합니다."] },
      { heading: "8. 정보주체의 권리", body: [
        "이용자는 개인정보 열람, 정정, 삭제, 처리정지 및 동의 철회를 요구할 수 있습니다. 설정 → 개인정보에서 데이터 내려받기, AI 학습 동의 변경, 회원 탈퇴를 직접 할 수 있으며, " + COMPANY.privacyEmail + "로 요청할 수도 있습니다.",
        "만 14세 미만 아동은 회원가입할 수 없습니다.",
      ] },
      { heading: "9. 쿠키", body: ["필수 쿠키만 사용합니다: 세션 쿠키(HttpOnly, 로그인), CSRF 토큰, 언어 설정, 비회원 체험 기기 쿠키. 광고 또는 사이트 간 추적 쿠키는 사용하지 않습니다."] },
      { heading: "10. 안전성 확보 조치", body: ["전송 구간 암호화(TLS), Argon2id 비밀번호 해시, 2단계 인증 및 패스키, 결제 빌링키 암호화 저장, 역할 기반 접근 통제 및 감사 로그, 최소 권한 모델 워커, 정기 보안 업데이트."] },
      { heading: "11. 개인정보 보호책임자", body: [`${COMPANY.privacyOfficer} · ${COMPANY.privacyEmail}. 문의에 지체 없이 답변합니다.`] },
      { heading: "12. 권익침해 구제방법", body: ["개인정보분쟁조정위원회(1833-6972, kopico.go.kr), 개인정보침해신고센터(118, privacy.kisa.or.kr), 대검찰청(1301), 경찰청 사이버수사국(182)."] },
      { heading: "13. 처리방침의 변경", body: ["변경 시 최소 7일 전(중요한 변경은 30일 전)에 공지합니다."] },
    ],
  },
}

export const REFUNDS: Record<Locale, LegalDoc> = {
  en: {
    title: "Refund Policy",
    intro: "This policy explains cancellations and refunds for subscriptions and credit packs, in line with the Act on the Consumer Protection in Electronic Commerce.",
    sections: [
      { heading: "1. Paid services", body: ["Subscriptions (Basic, Pro, Business) renew monthly and grant a monthly credit allowance. Credit packs are one-time purchases of prepaid credits."] },
      { heading: "2. Subscriptions", body: [
        "You can cancel at any time; renewal stops at the end of the current period and you keep its credits until then.",
        "Withdrawal within 7 days: if you request it within 7 days of payment and have not used any of that period’s credits, you receive a full refund.",
        "After use or after 7 days: refund = monthly fee × (remaining days ÷ days in the period).",
      ] },
      { heading: "3. Credit packs", body: [
        "Unused paid credits are refundable within 30 days of purchase: refund = amount paid × (unused paid credits ÷ purchased paid credits).",
        "Bonus credits included with a pack are not refundable and are removed when the pack is refunded.",
      ] },
      { heading: "4. Not refundable", body: ["Credits already used, expired periods or credits, free daily credits, the welcome bonus, promotional credits, credits obtained improperly, and cases excluded by law."] },
      { heading: "5. Our fault", body: ["If a payment error or a service failure on our side prevents you from using what you paid for, you receive a full refund regardless of usage. Analyses that fail are never charged in the first place."] },
      { heading: "6. How to request", body: [`Email ${COMPANY.supportEmail} with your order number (shown under Credits & billing → Payments). We respond within 3 business days. Refunds go to the original payment method; card refunds may take several business days to appear.`] },
      { heading: "7. Contact", body: [`${COMPANY.name} · ${COMPANY.supportEmail} · ${COMPANY.phone}`] },
    ],
  },
  ko: {
    title: "환불정책",
    intro: "본 정책은 「전자상거래 등에서의 소비자보호에 관한 법률」에 따라 구독 및 크레딧 팩의 청약철회와 환불 기준을 안내합니다.",
    sections: [
      { heading: "1. 유료 서비스", body: ["구독(베이직, 프로, 비즈니스)은 매월 자동 갱신되며 월간 크레딧을 제공합니다. 크레딧 팩은 선불 크레딧의 1회성 구매입니다."] },
      { heading: "2. 구독", body: [
        "언제든지 해지할 수 있으며, 해지 시 현재 기간 종료 후 갱신이 중단되고 해당 기간의 크레딧은 종료일까지 사용할 수 있습니다.",
        "7일 이내 청약철회: 결제일로부터 7일 이내에 요청하고 해당 기간의 크레딧을 사용하지 않은 경우 전액 환불합니다.",
        "사용 후 또는 7일 경과 후: 환불액 = 월 요금 × (잔여 일수 ÷ 해당 기간 일수).",
      ] },
      { heading: "3. 크레딧 팩", body: [
        "구매일로부터 30일 이내 미사용 유료 크레딧은 환불할 수 있습니다: 환불액 = 결제 금액 × (미사용 유료 크레딧 ÷ 구매한 유료 크레딧).",
        "팩에 포함된 보너스 크레딧은 환불되지 않으며, 팩 환불 시 함께 회수됩니다.",
      ] },
      { heading: "4. 환불 제한", body: ["이미 사용한 크레딧, 경과한 기간 또는 만료된 크레딧, 일일 무료 크레딧, 가입 보너스, 프로모션 크레딧, 부정한 방법으로 취득한 크레딧, 법령에서 제한하는 경우."] },
      { heading: "5. 회사 귀책 사유", body: ["결제 오류 또는 회사 측 장애로 결제한 서비스를 이용하지 못한 경우 사용 여부와 관계없이 전액 환불합니다. 분석에 실패한 작업은 애초에 크레딧이 차감되지 않습니다."] },
      { heading: "6. 신청 방법", body: [`주문번호(크레딧 및 결제 → 결제 내역)와 함께 ${COMPANY.supportEmail}로 요청해 주세요. 영업일 기준 3일 이내에 답변하며, 원 결제수단으로 환불됩니다. 카드 환불은 반영까지 영업일 기준 수일이 걸릴 수 있습니다.`] },
      { heading: "7. 문의", body: [`${COMPANY.name} · ${COMPANY.supportEmail} · ${COMPANY.phone}`] },
    ],
  },
}
