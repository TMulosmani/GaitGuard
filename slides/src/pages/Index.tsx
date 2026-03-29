import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Section } from '@/components/Section';
import { PillBase } from '@/components/ui/3d-adaptive-navigation-bar';
import PaperBackground from '@/components/PaperBackground';
import { LinesPatternCard, LinesPatternCardBody } from '@/components/ui/card-with-lines-pattern';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { useLanguage } from '@/contexts/LanguageContext';
const gaitguardLogo = '/logo_gaitguard_trimmed.png';

const problemCards = [
  {
    number: '200K+',
    text: 'ACL surgeries performed per year in the US alone.',
    citation: '(NCBI StatPearls, 2024; Biology Insights, 2024).',
    numberClassName: 'text-destructive',
    borderClassName: 'border-destructive/25',
    shadowClassName: 'shadow-[0_30px_80px_rgba(255,79,79,0.08)]',
  },
  {
    number: '1 in 4',
    text: 'ACL patients re-tear within 2 years of surgery.',
    citation: '(Princeton Medicine, 2024; MOON Knee ACL Research).',
    numberClassName: 'text-[#7fb0ff]',
    borderClassName: 'border-[#7fb0ff]/25',
    shadowClassName: 'shadow-[0_30px_80px_rgba(127,176,255,0.12)]',
  },
  {
    number: '70%',
    text: 'Of physical therapy patients fail to complete their full course of rehab.',
    citation: '(WebPT, 2024; JOSPT, 2024).',
    numberClassName: 'text-[#e4b24d]',
    borderClassName: 'border-[#e4b24d]/25',
    shadowClassName: 'shadow-[0_30px_80px_rgba(228,178,77,0.12)]',
  },
  {
    number: '$200-$500',
    text: 'Per clinical gait analysis session — unaffordable for regular monitoring.',
    citation: '(UCSF RunSafe Clinic; Celution Education, 2024).',
    numberClassName: 'text-primary',
    borderClassName: 'border-primary/25',
    shadowClassName: 'shadow-[0_30px_80px_rgba(74,159,212,0.12)]',
  },
];

const preReconCards = [
  {
    title: 'Baseline Capture',
    text: '2-minute standing-still phase at 50 Hz. Complementary filter (α=0.98) fuses accelerometer and gyro to lock in thigh, shin, and foot angle baselines.',
    citation: '(Winter, 2009; Madgwick et al., 2011).',
    accentClassName: 'text-primary',
    borderClassName: 'border-primary/30',
  },
  {
    title: 'Heel-Strike Detection',
    text: 'Triple-condition trigger: foot gyro <15°/s + accel_z within ±0.15g of 1g + knee within ±15° of baseline, held for ≥80ms. 300ms lockout prevents double-detection.',
    citation: '(Tao et al., 2012; Perry & Burnfield, 2010).',
    accentClassName: 'text-secondary',
    borderClassName: 'border-secondary/30',
  },
  {
    title: 'Stride Library',
    text: 'Valid strides (400–2500ms) are Butterworth low-pass filtered (6Hz, order 4) and time-normalized to 100 points. 20 strides = profile ready for twin generation.',
    citation: '(Winter, 2009; Butterworth, 1930).',
    accentClassName: 'text-accent',
    borderClassName: 'border-accent/30',
  },
];

const architectureCards = [
  {
    title: 'IMU Layer',
    text: 'Three MPU-6050 sensors (thigh, shin, foot) transmit via BLE at 50 Hz. Complementary filter fuses accel + gyro into joint angles. Swappable via IMUSource strategy pattern.',
    citation: '(Madgwick et al., 2011; InvenSense, 2013).',
    accentClassName: 'text-primary',
    borderClassName: 'border-primary/30',
  },
  {
    title: 'LSTM Digital Twin',
    text: '2-layer stacked LSTM (hidden=64) trained on 3000 normative healthy strides. Given the first 20% of a stride as anchor, predicts the healthy continuation for the remaining 80%.',
    citation: '(Hochreiter & Schmidhuber, 1997; Winter, 2009).',
    accentClassName: 'text-secondary',
    borderClassName: 'border-secondary/30',
  },
  {
    title: 'Scoring & Haptics',
    text: 'GHS = clamp(100 − dev_score × 25, 0–100). Three haptic patterns: TWO_SHORT (knee extension), ONE_LONG (foot clearance), THREE_SHORT (general deviation). Fires within the stride.',
    citation: '(Tao et al., 2012; Perry & Burnfield, 2010).',
    accentClassName: 'text-accent',
    borderClassName: 'border-accent/30',
  },
];

const workflowSteps = [
  { title: 'Calibrate', borderClassName: 'border-primary/30', arrowClassName: 'text-primary' },
  { title: 'Segment', borderClassName: 'border-secondary/30', arrowClassName: 'text-secondary' },
  { title: 'Twin', borderClassName: 'border-accent/30', arrowClassName: 'text-accent' },
  { title: 'Monitor', borderClassName: 'border-destructive/30', arrowClassName: 'text-destructive' },
];

const workflowArtifacts = [
  {
    title: 'Baseline Profile',
    text: '2-minute standing + walking calibration builds your personal joint angle baseline from thigh, shin, and foot IMUs.',
    citation: '(Winter, 2009; Madgwick et al., 2011).',
    accentClassName: 'text-primary',
    borderClassName: 'border-primary/30',
    bgClassName: 'bg-primary/10',
  },
  {
    title: 'Stride Library',
    text: '20 segmented strides with Butterworth-filtered knee and ankle waveforms form your Phase 1 gait profile.',
    citation: '(Perry & Burnfield, 2010; Tao et al., 2012).',
    accentClassName: 'text-secondary',
    borderClassName: 'border-secondary/30',
    bgClassName: 'bg-secondary/10',
  },
  {
    title: 'Digital Twin',
    text: 'A 2-layer LSTM trained on normative gait predicts your healthy continuation from each stride\'s first 20% anchor.',
    citation: '(Hochreiter & Schmidhuber, 1997; Winter, 2009).',
    accentClassName: 'text-accent',
    borderClassName: 'border-accent/30',
    bgClassName: 'bg-accent/10',
  },
  {
    title: 'Live Scoring',
    text: 'Every new stride is scored against the twin. GHS = 0–100. Deviations trigger targeted haptic patterns within the stride.',
    citation: '(Tao et al., 2012; Perry & Burnfield, 2010).',
    accentClassName: 'text-destructive',
    borderClassName: 'border-destructive/30',
    bgClassName: 'bg-destructive/10',
  },
];

const outputCards = [
  {
    title: 'Overlay Chart',
    text: 'Last 10 observed strides plotted against the healthy digital twin with ±1σ confidence band. Clinician sees exactly where the patient deviates.',
    citation: '(Winter, 2009; Perry & Burnfield, 2010).',
    accentClassName: 'text-primary',
    borderClassName: 'border-primary/30',
  },
  {
    title: 'GHS Trend Chart',
    text: 'Per-stride Gait Health Score colored green (≥80) / yellow (50–79) / red (<50). Immediate visual of session quality and progression.',
    citation: '(Tao et al., 2012).',
    accentClassName: 'text-secondary',
    borderClassName: 'border-secondary/30',
  },
  {
    title: 'Deviation Heatmap',
    text: 'S×80 matrix showing knee and ankle deviation at every timepoint across all monitored strides. Pinpoints which phase of gait is most impaired.',
    citation: '(Perry & Burnfield, 2010; Winter, 2009).',
    accentClassName: 'text-accent',
    borderClassName: 'border-accent/30',
  },
  {
    title: 'Session PDF Report',
    text: 'Auto-generated per session: cover page, methodology, all 3 charts, per-stride table, and haptic trigger log. Ready for clinician review or patient record.',
    citation: '(APTA Clinical Practice Guidelines, 2022).',
    accentClassName: 'text-destructive',
    borderClassName: 'border-destructive/30',
  },
];

const fixLoopCards = [
  {
    title: 'TWO_SHORT Pattern',
    badge: 'knee:extension-deficit',
    text: 'GaitGuard detects insufficient knee extension at heel strike (gait cycle 21–35%). Two short pulses prompt the patient to fully extend before weight-loading.',
    citation: '(Perry & Burnfield, 2010; Tao et al., 2012).',
    accentClassName: 'text-primary',
    borderClassName: 'border-primary/30',
  },
  {
    title: 'ONE_LONG Pattern',
    badge: 'ankle:clearance-deficit',
    text: 'Reduced plantarflexion push-off at swing phase (gait cycle 60–85%) triggers one long pulse — a cue to drive through the toe-off for foot clearance.',
    citation: '(Winter, 2009; Perry & Burnfield, 2010).',
    accentClassName: 'text-secondary',
    borderClassName: 'border-secondary/30',
  },
  {
    title: 'THREE_SHORT Pattern',
    badge: 'gait:high-deviation',
    text: 'When overall GHS drops below threshold across both joints, three short pulses signal general compensation — prompting the patient to slow down and reset.',
    citation: '(Tao et al., 2012; Winter, 2009).',
    accentClassName: 'text-accent',
    borderClassName: 'border-accent/30',
  },
];

const summaryCards = [
  {
    title: 'Clinically Grounded',
    text: 'Complementary filter fusion, Butterworth signal processing, and Winter (2009) normative gait data underpin every Gait Health Score.',
    citation: '(Winter, 2009; Madgwick et al., 2011; Butterworth, 1930).',
    accentClassName: 'text-primary',
    borderClassName: 'border-primary/30',
  },
  {
    title: 'Patient-Native',
    text: 'Real-time haptic feedback keeps correction inside the patient\'s movement loop instead of a post-session report that arrives too late.',
    citation: '(Tao et al., 2012; Perry & Burnfield, 2010).',
    accentClassName: 'text-secondary',
    borderClassName: 'border-secondary/30',
  },
  {
    title: 'Closed Loop',
    text: 'GaitGuard differentiates on personalized twin generation, per-stride deviation scoring, targeted haptic patterns, and session-level PDF reporting.',
    citation: '(Hochreiter & Schmidhuber, 1997; Winter, 2009).',
    accentClassName: 'text-accent',
    borderClassName: 'border-accent/30',
  },
];

const businessTiers = [
  {
    name: 'Free',
    price: '$0',
    period: '/mo',
    subtitle: 'Individual patients & researchers',
    features: [
      'Unlimited local sessions',
      'Session CSV export',
      'Basic GHS trend view',
      'Synthetic data mode',
      'Open-source pipeline',
    ],
    borderClassName: 'border-white/10',
    dotClassName: 'bg-primary',
    priceClassName: 'text-4xl md:text-5xl text-foreground',
    shadowClassName: 'shadow-[0_24px_70px_rgba(0,0,0,0.22)]',
  },
  {
    name: 'Clinic',
    price: '$99',
    period: '/mo',
    subtitle: 'Physical therapy & sports medicine',
    features: [
      'Multi-patient dashboard',
      'Session PDF reports',
      'LSTM twin per patient',
      'Haptic pattern configuration',
      'Clinic-branded reports',
    ],
    borderClassName: 'border-secondary/30',
    dotClassName: 'bg-secondary',
    priceClassName: 'text-4xl md:text-5xl text-secondary',
    shadowClassName: 'shadow-[0_24px_70px_rgba(47,107,168,0.12)]',
  },
  {
    name: 'Pro',
    price: '$299',
    period: '/mo',
    subtitle: 'High-volume rehab centers',
    features: [
      'Everything in Clinic',
      'Longitudinal progress tracking',
      'EHR-ready data export',
      'Team accounts & roles',
      'Priority support',
    ],
    borderClassName: 'border-primary/70',
    dotClassName: 'bg-primary',
    priceClassName: 'text-4xl md:text-5xl text-primary',
    shadowClassName: 'shadow-[0_32px_90px_rgba(74,159,212,0.18)]',
    badge: 'Most popular',
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    period: '',
    subtitle: 'Hospital systems & payer integrations',
    features: [
      'Custom LSTM training on institution data',
      'IRB-ready data exports',
      'SSO and audit logs',
      'VPC or on-premise deployment',
      'Clinical outcome reporting',
    ],
    borderClassName: 'border-accent/35',
    dotClassName: 'bg-accent',
    priceClassName: 'text-3xl md:text-4xl text-accent',
    shadowClassName: 'shadow-[0_24px_70px_rgba(126,200,232,0.12)]',
  },
];

const businessModelRows = [
  { label: 'Primary revenue', value: 'Monthly SaaS subscriptions (clinic-facing)' },
  { label: 'Secondary revenue', value: 'Hardware kit sales (~$150 margin per unit, <$500 retail)' },
  { label: 'Enterprise revenue', value: 'Hospital system contracts, payer integrations, CPT pathway' },
  { label: 'Pricing model', value: 'Platform fee + hardware kit' },
  { label: 'Billing', value: 'Monthly by default, annual discount available' },
  { label: 'Growth motion', value: 'Patient -> clinic adoption -> hospital system -> payer reimbursement' },
];

const upgradeRows = [
  { label: 'Free -> Clinic', value: 'Need multi-patient tracking and PDF reports' },
  { label: 'Clinic -> Pro', value: 'Need longitudinal tracking, EHR export, and team accounts' },
  { label: 'Pro -> Enterprise', value: 'Need SSO, IRB data exports, or on-premise deployment' },
  { label: 'Compliance trigger', value: 'Hospital credentialing or payer reimbursement requirement' },
  { label: 'Market benchmark', value: 'Vicon ~$12,500 system | Physitrack $21.99/mo/provider', isBadge: true },
];

const marketCards = [
  {
    title: 'TAM',
    value: '$50B',
    description: 'Global wearable medical device market',
    methodology: 'Grand View Research / MarketsandMarkets 2025; CAGR 25.5% → $168B by 2030',
    bullets: [
      '200,000+ ACL surgeries/year in the US; $7B annual ACL injury cost',
      'Wearable rehab tech demand spiked 34% from 2024–2026',
    ],
    borderClassName: 'border-[#5a98f2]/45',
    accentClassName: 'text-[#7fb0ff]',
    dotClassName: 'bg-[#4a90ff]',
    shadowClassName: 'shadow-[0_28px_80px_rgba(74,144,255,0.14)]',
  },
  {
    title: 'SAM',
    value: '$1.4B',
    description: 'Gait analysis devices + software market globally',
    methodology: 'Research and Markets 2025; CAGR 10.4% → $2.1B by 2029',
    bullets: [
      'AI-powered gait & mobility analytics: $950M (2025) → $1.67B (2030)',
      'PT + sports medicine clinics adopting outcomes-driven digital tools',
    ],
    borderClassName: 'border-primary/45',
    accentClassName: 'text-primary',
    dotClassName: 'bg-primary',
    shadowClassName: 'shadow-[0_28px_80px_rgba(74,159,212,0.14)]',
  },
  {
    title: 'SOM - Year 3',
    value: '$0.5M-$1.5M',
    description: 'Orthopedic rehab clinics + sports medicine practices adopting digital rehab tools',
    methodology: '5,000 reachable ACL-focused US clinics × 1% adoption × $3,000 ACV',
    bullets: [
      'Orthopedic rehab clinics seeing post-surgical ACL patients',
      'Sports medicine and athletic training programs with return-to-sport protocols',
    ],
    borderClassName: 'border-[#d9a441]/45',
    accentClassName: 'text-[#e4b24d]',
    dotClassName: 'bg-[#c88419]',
    shadowClassName: 'shadow-[0_28px_80px_rgba(217,164,65,0.14)]',
  },
];

const ganttMetrics = [
  { label: 'Traditional monitoring', value: '~1 hr/week', valueClassName: 'text-[#f27e73]' },
];

const ganttDays = Array.from({ length: 22 }, (_, index) => index + 1);

const traditionalWorkflowRows = [
  { label: 'Schedule clinic visit', dotClassName: 'bg-[#c83a36]', barClassName: 'bg-[#c83a36]', start: 1, span: 4, barLabel: '3–7 day wait' },
  { label: 'Clinician observes walking', dotClassName: 'bg-[#9b9a94]', barClassName: 'bg-[#a6a39c]', start: 5, span: 2, barLabel: 'Manual observation' },
  { label: 'Notes + subjective assessment', dotClassName: 'bg-[#c83a36]', barClassName: 'bg-[#c83a36]', start: 7, span: 3, barLabel: 'No quantification' },
  { label: 'Homework assigned', dotClassName: 'bg-[#9b9a94]', barClassName: 'bg-[#a6a39c]', start: 10, span: 4, barLabel: 'Adherence unknown' },
  { label: 'No data between sessions', dotClassName: 'bg-[#c83a36]', barClassName: 'bg-[#c83a36]', start: 14, span: 5, barLabel: '167 hrs unmonitored' },
  { label: 'Re-injury occurs', dotClassName: 'bg-[#9b9a94]', barClassName: 'bg-[#a6a39c]', start: 19, span: 2, barLabel: 'No warning given' },
  { label: 'Next visit (repeat cycle)', dotClassName: 'bg-[#c83a36]', barClassName: 'bg-[#c83a36]', start: 21, span: 2 },
];

const dispatchWorkflowRows = [
  { label: 'Strap 3 sensors (60 sec)', dotClassName: 'bg-[#1fb388]', barClassName: 'bg-[#1fb388]', start: 1, span: 1 },
  { label: 'Calibration walk (Phase 0+1)', dotClassName: 'bg-[#1fb388]', barClassName: 'bg-[#24b587]', start: 2, span: 1 },
  { label: 'LSTM twin generated (Phase 2)', dotClassName: 'bg-[#1fb388]', barClassName: 'bg-[#24b587]', start: 3, span: 1 },
  { label: 'Session begins — strides scored live', dotClassName: 'bg-[#1fb388]', barClassName: 'bg-[#24b587]', start: 4, span: 2 },
  { label: 'Haptic cue fires on deviation', dotClassName: 'bg-[#2f6fb6]', barClassName: 'bg-[#2f6fb6]', start: 6, span: 1 },
  { label: 'Session PDF + CSV generated', dotClassName: 'bg-[#1fb388]', barClassName: 'bg-[#24b587]', start: 7, span: 1 },
  { label: 'Clinician reviews remotely', dotClassName: 'bg-[#1fb388]', barClassName: 'bg-[#24b587]', start: 8, span: 1 },
];

const demoMoments = [
  'Patient straps three IMU sensors and stands still for a 2-minute calibration.',
  'GaitGuard segments 20 strides, filters and normalizes them, and builds the personal gait profile.',
  'The LSTM digital twin is generated from the healthy gait anchor — automatically.',
  'Every new stride is scored live. Haptic cues fire within the stride when deviations are detected.',
];

const competitorRows = [
  {
    tool: 'Vicon',
    description: 'Lab optical motion capture',
    pricing: '~$12,500+ system',
    features: ['no', 'no', 'no', 'no', 'no', 'no', 'yes'],
  },
  {
    tool: 'Biodex Gait Trainer 3',
    description: 'Instrumented treadmill',
    pricing: 'Enterprise (undisclosed)',
    features: ['no', 'partial', 'no', 'no', 'no', 'no', 'yes'],
  },
  {
    tool: 'DorsaVi ViMove+',
    description: 'Wearable IMU + AI analysis',
    pricing: 'Clinic contract',
    features: ['yes', 'no', 'no', 'no', 'no', 'yes', 'yes'],
  },
  {
    tool: 'XSENS / Movella',
    description: 'Research IMU capture',
    pricing: '$1K–$10K+',
    features: ['yes', 'no', 'no', 'no', 'no', 'yes', 'partial'],
  },
  {
    tool: 'Physitrack',
    description: 'PT exercise SaaS',
    pricing: '$10.99–$21.99/mo',
    features: ['no', 'no', 'no', 'no', 'no', 'no', 'yes'],
  },
  {
    tool: 'GaitGuard',
    description: 'Wearable + LSTM AI rehab',
    pricing: '<$500 HW + $0–$99/mo',
    features: ['yes', 'yes', 'yes', 'yes', 'yes', 'yes', 'yes'],
    isDispatch: true,
  },
];

const competitorColumns = [
  'Wearable',
  'Real-time feedback',
  'LSTM twin',
  'Per-stride scoring',
  'Haptic cues',
  'Portable',
  'Session report',
];

const forceCards = [
  {
    title: 'Threat of New Entrants',
    level: 'Medium',
    levelClassName: 'bg-[#5a4311] text-[#e4b24d]',
    barClassName: 'bg-[#d28a1d]',
    widthClassName: 'w-[55%]',
    text: 'AI + IMU hardware costs are falling. Moat comes from the LSTM training data flywheel and clinical validation — not the sensor hardware alone.',
  },
  {
    title: 'Bargaining Power of Buyers',
    level: 'Medium',
    levelClassName: 'bg-[#5a4311] text-[#e4b24d]',
    barClassName: 'bg-[#d28a1d]',
    widthClassName: 'w-[50%]',
    text: 'Clinics have limited alternatives for affordable real-time gait monitoring. Switching cost rises once GaitGuard is embedded in patient session workflow.',
  },
  {
    title: 'Bargaining Power of Suppliers',
    level: 'Low',
    levelClassName: 'bg-[#214b18] text-[#7fd14c]',
    barClassName: 'bg-[#15876d]',
    widthClassName: 'w-[20%]',
    text: 'MPU-6050 IMUs cost under $5 each. BLE modules are commoditized. No single supplier dependency. Cloud ML inference via PyTorch is fully portable.',
  },
  {
    title: 'Threat of Substitutes',
    level: 'Medium',
    levelClassName: 'bg-[#5a4311] text-[#e4b24d]',
    barClassName: 'bg-[#d28a1d]',
    widthClassName: 'w-[52%]',
    text: 'Manual observation, video review, and periodic in-lab gait analysis (Vicon, Biodex) are the current standard — but none provide real-time per-stride haptic feedback.',
  },
  {
    title: 'Competitive Rivalry',
    level: 'Low–Medium',
    levelClassName: 'bg-[#214b18] text-[#7fd14c]',
    barClassName: 'bg-[#15876d]',
    widthClassName: 'w-[35%]',
    text: "Lab systems (Vicon, Biodex) don't compete on portability or price. Wearable competitors (DorsaVi) lack LSTM twins and haptic feedback. No direct equivalent exists today.",
    fullWidth: true,
  },
];

const Citation = ({ text, className = '' }: { text: string; className?: string }) => (
  <p className={`mt-4 text-xs leading-relaxed tracking-wide text-muted-foreground/70 ${className}`}>
    {text}
  </p>
);

const MAIN_NAV_ITEMS = [
  { label: 'Home', id: 'home' },
  { label: 'Problem', id: 'problem' },
  { label: 'GaitGuard', id: 'how-it-works' },
  { label: 'Demo', id: 'demo' },
  { label: 'Output', id: 'pdf-output' },
  { label: 'Market', id: 'market-size' },
  { label: 'Competition', id: 'competition' },
  { label: 'Conclusion', id: 'conclusion' },
];

const APPENDIX_NAV_ITEMS = [
  { label: 'Five Forces', id: 'five-forces' },
  { label: 'Summary', id: 'summary' },
  { label: 'Business', id: 'business-model' },
  { label: 'Timeline', id: 'timeline' },
  { label: 'EVA', id: 'eva' },
  { label: 'Calibration', id: 'clinical' },
  { label: 'Architecture', id: 'solution' },
  { label: 'Outputs', id: 'dashboard' },
  { label: 'Feedback Loop', id: 'muscle' },
];

const SECTION_IDS = [...MAIN_NAV_ITEMS.map((item) => item.id), ...APPENDIX_NAV_ITEMS.map((item) => item.id)];

const Index = () => {
  const { t } = useLanguage();
  const [activeSection, setActiveSection] = useState('home');
  const [appendixOpen, setAppendixOpen] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const teamMembers = [
    { name: 'Arsh Singh', role: 'Computer Science', initials: 'A', image: '/arsh.jpeg' },
    { name: 'Paul Trusov', role: 'Computer Science, Cornell University', initials: 'P', image: '/paultrusov.jpeg' },
    { name: 'Sam Rosen', role: 'Mechanical Engineering, University of New Haven', initials: 'S', image: '/samrosen.jpeg' },
    { name: 'Jimmy Mulosmani', role: 'Computer Science', initials: 'J', image: '/Jimmy_Headshot.jpeg' },
  ];

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const scrollTop = container.scrollTop;
      const viewportH = container.clientHeight;
      const scrollMid = scrollTop + viewportH / 2;

      for (const sectionId of SECTION_IDS) {
        const el = document.getElementById(sectionId);
        if (el) {
          const top = el.offsetTop;
          if (scrollMid >= top && scrollMid < top + el.offsetHeight) {
            setActiveSection(sectionId);
            break;
          }
        }
      }
    };

    container.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => container.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (sectionId: string) => {
    const element = document.getElementById(sectionId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="relative min-h-screen">
      <PaperBackground />

      <div className="fixed top-8 left-1/2 z-50 -translate-x-1/2">
        <PillBase activeSection={activeSection} navItems={MAIN_NAV_ITEMS} onSectionClick={scrollToSection} />
      </div>

      <div className="fixed bottom-6 right-6 z-[70]">
        {appendixOpen ? (
          <LinesPatternCard className="w-52 rounded-2xl border border-primary/35 bg-card/95 shadow-[0_28px_80px_rgba(0,0,0,0.38)] backdrop-blur-md">
            <LinesPatternCardBody className="p-3">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold tracking-[0.18em] uppercase text-primary">Appendix</p>
                <button
                  type="button"
                  onClick={() => setAppendixOpen(false)}
                  className="text-muted-foreground hover:text-foreground transition text-lg leading-none"
                >
                  ×
                </button>
              </div>
              <div className="mt-2 flex flex-col gap-1.5">
                {APPENDIX_NAV_ITEMS.map((item) => {
                  const isActive = activeSection === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => scrollToSection(item.id)}
                      className={`rounded-md px-2 py-1 text-left text-sm transition ${
                        isActive
                          ? 'bg-primary/25 text-primary'
                          : 'text-muted-foreground hover:bg-primary/15 hover:text-foreground'
                      }`}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>
            </LinesPatternCardBody>
          </LinesPatternCard>
        ) : (
          <button
            type="button"
            onClick={() => setAppendixOpen(true)}
            className="flex h-10 w-10 items-center justify-center rounded-full border border-primary/35 bg-card/95 text-primary shadow-[0_12px_30px_rgba(0,0,0,0.3)] backdrop-blur-md transition hover:bg-primary/15 hover:scale-105"
            title="Appendix"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        )}
      </div>

      {activeSection === 'conclusion' && (
        <div className="fixed bottom-6 left-6 z-[70] flex flex-col items-center gap-2">
          <div className="rounded-2xl bg-white p-3 shadow-lg">
            <img
              src="https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=https://github.com/TMulosmani/GaitGuard&bgcolor=ffffff&color=000000"
              alt="GitHub QR Code"
              className="h-36 w-36"
            />
          </div>
          <p className="text-sm text-muted-foreground font-semibold">GitHub</p>
        </div>
      )}

      <div ref={scrollContainerRef} className="snap-y snap-mandatory h-screen overflow-y-scroll scrollbar-hide relative">
        <Section id="home" className="bg-transparent" contentClassName="max-w-7xl py-16 lg:py-20">
          <div className="space-y-12">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
              className="mx-auto max-w-6xl text-center"
            >
              <img
                src={gaitguardLogo}
                alt={t('home.title')}
                className="mx-auto w-full max-w-[23rem] sm:max-w-[26rem] md:max-w-[30rem] xl:max-w-[36rem] object-contain drop-shadow-[0_28px_50px_rgba(0,0,0,0.3)]"
              />
            </motion.div>

            <div className="grid gap-8 md:grid-cols-2 xl:grid-cols-4 max-w-7xl mx-auto mt-14">
              {teamMembers.map((member, index) => (
                <motion.div
                  key={member.name}
                  initial={{ opacity: 0, y: 50 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.8, delay: 0.2 + index * 0.15 }}
                >
                  <LinesPatternCard
                    className="h-[24rem] rounded-[2rem] shadow-2xl"
                    patternClassName="h-full overflow-hidden rounded-[1.25rem]"
                    gradientClassName="h-full overflow-hidden rounded-[1.25rem]"
                  >
                    <LinesPatternCardBody className="h-full rounded-[1.25rem] bg-gradient-to-br from-primary/10 to-secondary/5 p-0 md:p-0">
                      <div className="flex h-full flex-col items-center px-5 py-8 text-center sm:px-6">
                        {member.image ? (
                          <div className="flex h-36 items-center justify-center">
                            <div className="h-32 w-32 overflow-hidden rounded-full border border-primary/20 shadow-sm">
                              <img
                                src={member.image}
                                alt={member.name}
                                className="h-full w-full object-cover"
                              />
                            </div>
                          </div>
                        ) : (
                          <div className="flex h-36 items-center justify-center">
                            <div className="flex h-32 w-32 items-center justify-center rounded-full border border-primary/20 bg-background/80 text-3xl font-bold text-primary shadow-sm">
                              {member.initials}
                            </div>
                          </div>
                        )}
                        <div className="mt-6 flex min-h-[7.5rem] w-full flex-col items-center">
                          <p className="text-xl leading-tight text-foreground font-semibold">{member.name}</p>
                          <p className="mt-3 w-full text-[0.95rem] leading-tight text-muted-foreground">{member.role}</p>
                          <p className="mt-2 text-sm font-bold tracking-wide text-foreground">
                            Cornell University
                          </p>
                        </div>
                      </div>
                    </LinesPatternCardBody>
                  </LinesPatternCard>
                </motion.div>
              ))}
            </div>

            <motion.p
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
              className="mx-auto mt-10 w-fit whitespace-nowrap text-center text-xl font-light leading-none text-muted-foreground md:text-2xl xl:text-[2rem]"
            >
              {t('home.subtitle')}
            </motion.p>
          </div>
        </Section>

        <Section id="problem" className="bg-transparent" contentClassName="max-w-[92rem] py-3">
          <div className="space-y-3">
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
              viewport={{ once: false, amount: 0.35 }}
              className="mx-auto max-w-6xl text-center"
            >
              <h2 className="text-3xl font-black tracking-tight leading-[1.05] text-foreground md:text-5xl xl:text-6xl">
                Gait rehab is <span className="text-destructive">flying blind</span>.
              </h2>
              <p className="mx-auto mt-3 max-w-5xl text-lg leading-relaxed text-muted-foreground md:text-xl">
                Clinicians see patients once a week. The other 167 hours? Nobody is watching.
              </p>
            </motion.div>

            <div className="grid max-w-7xl mx-auto gap-2.5 md:grid-cols-2 xl:grid-cols-4">
              {problemCards.map((card, index) => (
                <motion.div
                  key={card.number}
                  initial={{ opacity: 0, y: 28 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: 0.08 * index }}
                  viewport={{ once: false, amount: 0.3 }}
                  className={`h-full rounded-[1.5rem] border bg-card/90 px-4 py-4 backdrop-blur-md ${card.borderClassName} ${card.shadowClassName}`}
                >
                  <div className={`text-4xl font-black tracking-tight md:text-5xl ${card.numberClassName}`}>
                    {card.number}
                  </div>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground md:text-base">
                    {card.text}
                  </p>
                  <Citation text={card.citation} className="!mt-1.5" />
                </motion.div>
              ))}
            </div>

            <motion.div
              initial={{ opacity: 0, y: 28 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.55, delay: 0.18 }}
              viewport={{ once: false, amount: 0.25 }}
            >
              <LinesPatternCard className="max-w-5xl mx-auto rounded-[1.75rem] border-primary/30 shadow-[0_30px_90px_rgba(33,117,78,0.22)]">
                <LinesPatternCardBody className="p-5 md:p-6">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-5">
                      <p className="text-lg font-semibold text-destructive mb-1">Traditional Rehab</p>
                      <p className="text-4xl md:text-5xl font-black text-destructive">~1 hr/week</p>
                      <p className="mt-3 text-base text-muted-foreground leading-relaxed">
                        In-clinic only. Gait assessed once or twice per rehab cycle. No feedback between sessions. Patient re-injures with no warning. $500/session, 6–18 month recovery, 1 in 4 re-tears.
                      </p>
                      <Citation text="(Princeton Medicine, 2024; WebPT, 2024; UCSF RunSafe Clinic)." className="!mt-2" />
                    </div>
                    <div className="rounded-xl border border-primary/30 bg-primary/5 p-5">
                      <p className="text-lg font-semibold text-primary mb-1">With GaitGuard</p>
                      <p className="text-4xl md:text-5xl font-black text-primary">Every stride</p>
                      <p className="mt-3 text-base text-muted-foreground leading-relaxed">
                        Continuous wearable monitoring every session. Real-time haptic cues correct errors as they happen. LSTM digital twin tracks progress toward healthy gait. Rehab guided by data, not memory.
                      </p>
                      <Citation text="(Tao et al., 2012; Hochreiter & Schmidhuber, 1997)." className="!mt-2" />
                    </div>
                  </div>
                </LinesPatternCardBody>
              </LinesPatternCard>
            </motion.div>
          </div>
        </Section>

        <Section id="how-it-works" className="bg-transparent" contentClassName="max-w-7xl py-6">
          <div className="space-y-5">
            <div className="text-center space-y-3">
              <h1 className="text-3xl font-bold text-foreground md:text-5xl xl:text-6xl">
                <span className="text-primary">GaitGuard</span> learns your healthy gait — then <span className="text-primary">guards</span> it, in real time.
              </h1>
              <p className="max-w-5xl mx-auto text-lg md:text-xl text-muted-foreground">
                Strap on three sensors. Walk for 2 minutes. GaitGuard builds your personal healthy twin and monitors every stride from there.
              </p>
            </div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="flex flex-wrap items-center justify-center gap-2.5 max-w-6xl mx-auto"
            >
              {workflowSteps.map((step, index) => (
                <div key={step.title} className="flex items-center gap-2.5">
                  <LinesPatternCard className={`rounded-lg shadow-lg ${step.borderClassName}`}>
                    <LinesPatternCardBody className="flex h-12 items-center justify-center px-3 py-2 text-center">
                      <p className="text-lg font-semibold text-foreground whitespace-nowrap">{step.title}</p>
                    </LinesPatternCardBody>
                  </LinesPatternCard>

                  {index < workflowSteps.length - 1 && (
                    <div className={`text-xl font-bold ${step.arrowClassName}`}>→</div>
                  )}
                </div>
              ))}
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.15 }}
            >
              <LinesPatternCard className="rounded-xl shadow-2xl border-primary/40 max-w-7xl mx-auto">
                <LinesPatternCardBody className="p-5">
                  <h3 className="text-2xl md:text-3xl font-bold text-foreground mb-5 text-center">Artifacts at each stage</h3>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    {workflowArtifacts.map((artifact) => (
                      <div
                        key={artifact.title}
                        className={`rounded-xl border p-4 text-left ${artifact.bgClassName} ${artifact.borderClassName}`}
                      >
                        <p className={`text-xl md:text-2xl font-semibold ${artifact.accentClassName}`}>{artifact.title}</p>
                        <p className="mt-2 text-sm md:text-base leading-relaxed text-foreground">{artifact.text}</p>
                        <Citation text={artifact.citation} className="!mt-1.5" />
                      </div>
                    ))}
                  </div>
                </LinesPatternCardBody>
              </LinesPatternCard>
            </motion.div>

            <LinesPatternCard className="max-w-5xl mx-auto rounded-xl shadow-2xl border-primary/25">
              <LinesPatternCardBody className="p-4 text-center">
                <p className="text-2xl md:text-3xl font-semibold text-foreground leading-snug">
                  Not just a <span className="text-destructive">score</span> — a <span className="text-primary">haptic cue</span> at the exact moment the error happens.
                </p>
              </LinesPatternCardBody>
            </LinesPatternCard>
          </div>
        </Section>

        <Section id="demo" className="bg-transparent" contentClassName="max-w-6xl py-10">
          <div className="space-y-6">
            <div className="text-center">
              <h1 className="text-4xl md:text-6xl font-bold text-foreground">
                <span className="text-primary">GaitGuard</span> Live Demo
              </h1>
            </div>
            <div className="rounded-2xl overflow-hidden border border-primary/30 bg-black shadow-[0_30px_90px_rgba(0,0,0,0.4)]">
              <video
                className="w-full h-auto"
                controls
                playsInline
                preload="metadata"
              >
                <source src="/demo.mp4" type="video/mp4" />
                Your browser does not support the video tag.
              </video>
            </div>
          </div>
        </Section>

        <Section id="pdf-output" className="bg-transparent" contentClassName="max-w-6xl py-10">
          <div className="space-y-6">
            <div className="text-center">
              <h1 className="text-4xl md:text-6xl font-bold text-foreground">
                <span className="text-primary">GaitGuard</span> Session Report
              </h1>
              <p className="mt-3 text-lg md:text-xl text-muted-foreground">
                Auto-generated per-session PDF with Gait Health Score trend, observed vs. digital twin overlay, deviation heatmap, and haptic trigger log.
              </p>
            </div>
            <div className="rounded-2xl overflow-hidden border border-primary/30 bg-white shadow-[0_30px_90px_rgba(0,0,0,0.4)]" style={{ height: '70vh' }}>
              <iframe
                src="/dispatch-output.pdf"
                className="w-full h-full"
                title="GaitGuard Session Report"
              />
            </div>
          </div>
        </Section>

        <Section id="market-size" className="bg-transparent">
          <div className="space-y-8">
            <div className="text-center space-y-4">
              <h1 className="text-5xl md:text-7xl font-bold text-foreground">Market Size</h1>
              <p className="max-w-5xl mx-auto text-xl md:text-2xl text-muted-foreground">
                Year 3: $500K–$1.5M ARR. Expanding into a $1.4B wearable gait analysis market growing at 10% CAGR.
              </p>
            </div>

            <div className="grid max-w-7xl mx-auto gap-6 lg:grid-cols-3">
              {marketCards.map((card, index) => (
                <motion.div
                  key={card.title}
                  initial={{ opacity: 0, y: 28 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.55, delay: 0.1 * index }}
                >
                  <div className={`h-full rounded-[2rem] border bg-card/90 px-8 py-10 backdrop-blur-md ${card.borderClassName} ${card.shadowClassName}`}>
                    <p className={`text-2xl md:text-3xl font-semibold tracking-[0.12em] uppercase ${card.accentClassName}`}>
                      {card.title}
                    </p>
                    <div className={`mt-6 text-3xl md:text-4xl font-black tracking-tight ${card.accentClassName}`}>
                      {card.value}
                    </div>
                    <p className="mt-6 text-xl md:text-2xl leading-relaxed text-muted-foreground">
                      {card.description}
                    </p>
                    {card.methodology && (
                      <p className="mt-3 text-sm leading-relaxed text-muted-foreground/70 font-mono bg-white/5 rounded-lg px-3 py-2">
                        {card.methodology}
                      </p>
                    )}

                    <div className="mt-8 border-t border-border/60 pt-6">
                      <ul className="space-y-5">
                        {card.bullets.map((bullet) => (
                          <li key={bullet} className="flex items-start gap-3 text-xl leading-relaxed text-foreground/90">
                            <span className={`mt-2.5 h-2.5 w-2.5 shrink-0 rounded-full ${card.dotClassName}`} />
                            <span>{bullet}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        </Section>

        <Section id="competition" className="bg-transparent" contentClassName="max-w-7xl py-6">
          <div className="space-y-4">
            <div className="text-center space-y-1">
              <h1 className="text-4xl md:text-6xl font-bold text-foreground">Competitive Landscape</h1>
              <p className="max-w-5xl mx-auto text-lg md:text-xl text-muted-foreground">
                Others require a lab or cost six figures. GaitGuard brings clinical-grade gait analysis to every session for under $500 in hardware.
              </p>
            </div>

            <LinesPatternCard className="rounded-[1.5rem] shadow-2xl border-primary/25">
              <LinesPatternCardBody className="p-4 md:p-5">
                <div className="overflow-x-auto">
                  <table className="min-w-[1100px] w-full text-left">
                    <thead>
                      <tr className="border-b border-border/60 text-sm md:text-base text-muted-foreground">
                        <th className="pb-3 pr-4 font-semibold">Tool</th>
                        <th className="pb-3 px-4 font-semibold">Pricing</th>
                        {competitorColumns.map((column) => (
                          <th key={column} className="pb-3 px-3 text-center font-semibold">
                            {column}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {competitorRows.map((row) => (
                        <tr
                          key={row.tool}
                          className={`border-b border-border/50 ${row.isDispatch ? 'bg-primary/18 ring-1 ring-primary/50' : ''}`}
                        >
                          <td className="py-4 pr-4 align-top">
                            <div className={`${row.isDispatch ? 'text-primary' : 'text-foreground'} text-xl font-bold`}>
                              {row.tool}
                            </div>
                            <div className="text-sm md:text-base text-muted-foreground">
                              {row.description}
                            </div>
                          </td>
                          <td className={`py-4 px-4 align-top text-base md:text-lg font-semibold ${row.isDispatch ? 'text-primary' : 'text-foreground/85'}`}>
                            {row.pricing}
                          </td>
                          {row.features.map((feature, index) => (
                            <td key={`${row.tool}-${competitorColumns[index]}`} className="py-4 px-3 text-center align-top">
                              {feature === 'yes' ? (
                                <span className={`text-3xl leading-none ${row.isDispatch ? 'text-primary' : 'text-[#4A9FD4]'}`}>✓</span>
                              ) : feature === 'partial' ? (
                                <span className="text-lg font-semibold text-[#d99321]">Partial</span>
                              ) : (
                                <span className="text-3xl leading-none text-muted-foreground/55">×</span>
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-6 text-sm md:text-base">
                  <div className="flex items-center gap-2 text-foreground/90">
                    <span className="text-2xl text-[#4A9FD4]">✓</span>
                    <span>Yes</span>
                  </div>
                  <div className="flex items-center gap-2 text-foreground/90">
                    <span className="font-semibold text-[#d99321]">Partial</span>
                    <span>Partial</span>
                  </div>
                  <div className="flex items-center gap-2 text-foreground/90">
                    <span className="text-2xl text-muted-foreground/55">×</span>
                    <span>No</span>
                  </div>
                  <div className="font-semibold text-muted-foreground">
                    Gap: nobody else combines a personalized healthy digital twin with real-time per-stride haptic correction in a portable, affordable package.
                  </div>
                </div>
              </LinesPatternCardBody>
            </LinesPatternCard>
          </div>
        </Section>

        <Section id="conclusion" className="bg-transparent" contentClassName="max-w-7xl py-16 lg:py-20">
          <div className="space-y-12">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
              className="mx-auto max-w-6xl text-center"
            >
              <img
                src={gaitguardLogo}
                alt="GaitGuard"
                className="mx-auto w-full max-w-[23rem] sm:max-w-[26rem] md:max-w-[30rem] xl:max-w-[36rem] object-contain drop-shadow-[0_28px_50px_rgba(0,0,0,0.3)]"
              />
            </motion.div>

            <div className="grid gap-8 md:grid-cols-2 xl:grid-cols-4 max-w-7xl mx-auto">
              {teamMembers.map((member, index) => (
                <motion.div
                  key={member.name}
                  initial={{ opacity: 0, y: 50 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.8, delay: 0.2 + index * 0.15 }}
                >
                  <LinesPatternCard
                    className="h-[24rem] rounded-[2rem] shadow-2xl"
                    patternClassName="h-full overflow-hidden rounded-[1.25rem]"
                    gradientClassName="h-full overflow-hidden rounded-[1.25rem]"
                  >
                    <LinesPatternCardBody className="h-full rounded-[1.25rem] bg-gradient-to-br from-primary/10 to-secondary/5 p-0 md:p-0">
                      <div className="flex h-full flex-col items-center px-5 py-8 text-center sm:px-6">
                        {member.image ? (
                          <div className="flex h-36 items-center justify-center">
                            <div className="h-32 w-32 overflow-hidden rounded-full border border-primary/20 shadow-sm">
                              <img
                                src={member.image}
                                alt={member.name}
                                className="h-full w-full object-cover"
                              />
                            </div>
                          </div>
                        ) : (
                          <div className="flex h-36 items-center justify-center">
                            <div className="flex h-32 w-32 items-center justify-center rounded-full border border-primary/20 bg-background/80 text-3xl font-bold text-primary shadow-sm">
                              {member.initials}
                            </div>
                          </div>
                        )}
                        <div className="mt-6 flex min-h-[7.5rem] w-full flex-col items-center">
                          <p className="text-xl leading-tight text-foreground font-semibold">{member.name}</p>
                          <p className="mt-3 w-full text-[0.95rem] leading-tight text-muted-foreground">{member.role}</p>
                          <p className="mt-2 text-sm font-bold tracking-wide text-foreground">
                            Cornell University
                          </p>
                        </div>
                      </div>
                    </LinesPatternCardBody>
                  </LinesPatternCard>
                </motion.div>
              ))}
            </div>

            <motion.div
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
              className="text-center"
            >
              <p className="text-3xl md:text-4xl font-bold text-foreground">
                Gait rehab shouldn't require a $12,000 lab. <span className="text-primary">We built the lab into a wristband</span>.
              </p>
            </motion.div>

          </div>
        </Section>

        <Section id="five-forces" className="bg-transparent" contentClassName="max-w-7xl py-6">
          <div className="space-y-4">
            <div className="text-center space-y-1">
              <h1 className="text-4xl md:text-6xl font-bold text-foreground">Porter's Five Forces</h1>
              <p className="max-w-5xl mx-auto text-lg md:text-xl text-muted-foreground">
                Market dynamics shaping the wearable gait rehabilitation space.
              </p>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              {forceCards.filter((card) => !card.fullWidth).map((card) => (
                <LinesPatternCard key={card.title} className="rounded-[1.5rem] shadow-xl border-white/10">
                  <LinesPatternCardBody className="p-5">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="text-xl md:text-2xl font-bold text-foreground">{card.title}</h3>
                      <span className={`rounded-full px-4 py-1 text-sm md:text-base font-semibold ${card.levelClassName}`}>
                        {card.level}
                      </span>
                    </div>
                    <div className="mt-4 h-3 rounded-full bg-white/12">
                      <div className={`h-3 rounded-full ${card.barClassName} ${card.widthClassName}`} />
                    </div>
                    <p className="mt-4 text-lg leading-relaxed text-muted-foreground">{card.text}</p>
                  </LinesPatternCardBody>
                </LinesPatternCard>
              ))}
            </div>

            {forceCards.filter((card) => card.fullWidth).map((card) => (
              <LinesPatternCard key={card.title} className="rounded-[1.5rem] shadow-2xl border-white/10">
                <LinesPatternCardBody className="p-5">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="text-2xl md:text-3xl font-bold text-foreground">{card.title}</h3>
                    <span className={`rounded-full px-4 py-1 text-sm md:text-base font-semibold ${card.levelClassName}`}>
                      {card.level}
                    </span>
                  </div>
                  <div className="mt-4 h-3 rounded-full bg-white/12">
                    <div className={`h-3 rounded-full ${card.barClassName} ${card.widthClassName}`} />
                  </div>
                  <p className="mt-4 text-xl leading-relaxed text-muted-foreground">
                    {card.text}
                  </p>
                  <div className="mt-5 flex flex-wrap gap-3">
                    <span className="rounded-full bg-[#1d3658] px-4 py-2 text-base font-semibold text-[#83b3ff]">Snyk: $25-$40/dev/mo</span>
                    <span className="rounded-full bg-[#1d3658] px-4 py-2 text-base font-semibold text-[#83b3ff]">Semgrep: freemium OSS</span>
                    <span className="rounded-full bg-[#1d3658] px-4 py-2 text-base font-semibold text-[#83b3ff]">GitHub Adv. Security: bundled</span>
                  </div>
                </LinesPatternCardBody>
              </LinesPatternCard>
            ))}
          </div>
        </Section>

        <Section id="summary" className="bg-transparent" contentClassName="max-w-6xl py-12">
          <div className="space-y-6">
            <div className="text-center space-y-3">
              <h1 className="text-5xl md:text-6xl font-bold text-foreground">Why GaitGuard Stands Out</h1>
              <p className="max-w-5xl mx-auto text-xl md:text-2xl text-muted-foreground">
                GaitGuard is not just a sensor. It is a personalized rehabilitation co-pilot built on top of real-time biomechanical intelligence.
              </p>
            </div>

            <div className="grid gap-5 max-w-7xl mx-auto md:grid-cols-3">
              {summaryCards.map((card, index) => (
                <motion.div
                  key={card.title}
                  initial={{ opacity: 0, y: 28 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.55, delay: 0.1 * index }}
                >
                  <LinesPatternCard className={`rounded-2xl shadow-xl h-full ${card.borderClassName}`}>
                    <LinesPatternCardBody className="p-6">
                      <h3 className={`text-2xl font-bold mb-3 ${card.accentClassName}`}>{card.title}</h3>
                      <p className="text-foreground text-lg leading-relaxed">{card.text}</p>
                      <Citation text={card.citation} className="!mt-2" />
                    </LinesPatternCardBody>
                  </LinesPatternCard>
                </motion.div>
              ))}
            </div>

            <LinesPatternCard className="max-w-6xl mx-auto rounded-2xl shadow-2xl border-primary/30">
              <LinesPatternCardBody className="p-7 text-center">
                <p className="text-3xl md:text-4xl font-bold text-foreground leading-tight">
                  Rehab tools give you a weekly summary. GaitGuard corrects you mid-stride.
                </p>
                <p className="mt-3 text-lg md:text-xl text-muted-foreground max-w-4xl mx-auto leading-relaxed">
                  The next step is clear: integrate real patient data from COMPWALK and clinical cohorts, validate with IRB studies, and expand haptic patterns to cover the full lower-limb kinematic chain.
                </p>
                <Citation
                  text={'(Winter, 2009; Tao et al., 2012; Hochreiter & Schmidhuber, 1997).'}
                  className="text-center !mt-2"
                />
              </LinesPatternCardBody>
            </LinesPatternCard>
          </div>
        </Section>

        <Section id="business-model" className="bg-transparent" contentClassName="max-w-7xl py-6">
          <div className="space-y-4">
            <div className="text-center space-y-1">
              <h1 className="text-4xl md:text-5xl font-bold text-foreground">GaitGuard Business Model</h1>
              <p className="max-w-5xl mx-auto text-base md:text-lg text-muted-foreground">
                Hardware kit for the clinic. Software subscription for the data. Enterprise for hospital systems and payer integration.
              </p>
              <Citation
                text={'(Grand View Research, 2025; MarketsandMarkets, 2025; Physitrack Pricing, 2025).'}
                className="text-center !mt-1"
              />
            </div>

            <div className="grid max-w-7xl mx-auto gap-4 md:grid-cols-2 xl:grid-cols-4">
              {businessTiers.map((tier, index) => (
                <motion.div
                  key={tier.name}
                  initial={{ opacity: 0, y: 28 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.55, delay: 0.08 * index }}
                  className="relative"
                >
                  {tier.badge ? (
                    <div className="absolute left-1/2 top-0 z-10 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary px-4 py-1 text-xs font-semibold text-primary-foreground shadow-[0_18px_40px_rgba(74,159,212,0.25)]">
                      {tier.badge}
                    </div>
                  ) : null}
                  <div className={`h-full rounded-[1.5rem] border bg-card/90 px-5 py-5 backdrop-blur-md ${tier.borderClassName} ${tier.shadowClassName}`}>
                    <p className="text-xl font-bold text-foreground">{tier.name}</p>
                    <div className="mt-2 flex items-end gap-1">
                      <span className={`font-black tracking-tight ${tier.priceClassName}`}>{tier.price}</span>
                      {tier.period ? (
                        <span className="pb-1 text-xl font-semibold text-muted-foreground">{tier.period}</span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{tier.subtitle}</p>

                    <div className="mt-3 border-t border-border/60 pt-3">
                      <ul className="space-y-1.5">
                        {tier.features.map((feature) => (
                          <li key={feature} className="flex items-start gap-2 text-sm">
                            <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${tier.dotClassName}`} />
                            <span className="text-foreground/90">{feature}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>

            <div className="grid max-w-7xl mx-auto gap-4 lg:grid-cols-2">
              <LinesPatternCard className="rounded-[1.5rem] shadow-2xl border-primary/25">
                <LinesPatternCardBody className="p-5">
                  <h3 className="text-xl md:text-2xl font-bold text-foreground mb-3">How GaitGuard makes money</h3>
                  <div className="space-y-1.5">
                    {businessModelRows.map((row) => (
                      <div
                        key={row.label}
                        className="flex flex-col gap-1 border-b border-border/60 pb-1.5 md:flex-row md:items-center md:justify-between"
                      >
                        <span className="text-sm md:text-base text-muted-foreground">{row.label}</span>
                        <span className="text-sm md:text-base font-semibold text-foreground md:text-right">{row.value}</span>
                      </div>
                    ))}
                  </div>
                </LinesPatternCardBody>
              </LinesPatternCard>

              <LinesPatternCard className="rounded-[1.5rem] shadow-2xl border-secondary/30">
                <LinesPatternCardBody className="p-5">
                  <h3 className="text-xl md:text-2xl font-bold text-foreground mb-3">Upgrade triggers and market anchors</h3>
                  <div className="space-y-1.5">
                    {upgradeRows.map((row) => (
                      <div
                        key={row.label}
                        className="flex flex-col gap-1 border-b border-border/60 pb-1.5 md:flex-row md:items-center md:justify-between"
                      >
                        <span className="text-sm md:text-base text-muted-foreground">{row.label}</span>
                        {row.isBadge ? (
                          <span className="inline-flex items-center rounded-full bg-primary/15 px-3 py-1 text-sm font-semibold text-primary">
                            {row.value}
                          </span>
                        ) : (
                          <span className="text-sm md:text-base font-semibold text-foreground md:text-right">{row.value}</span>
                        )}
                      </div>
                    ))}
                  </div>
                  <Citation
                    text={'(Vicon, 2025; DorsaVi, 2025; Physitrack Pricing, 2025; Research and Markets, 2025).'}
                    className="!mt-2"
                  />
                </LinesPatternCardBody>
              </LinesPatternCard>
            </div>
          </div>
        </Section>

        <Section id="timeline" className="bg-transparent" contentClassName="max-w-7xl py-6">
          <div className="space-y-6">
            <div className="text-center space-y-2">
              <h1 className="text-4xl md:text-6xl font-bold text-foreground">Rehab Monitoring: Traditional vs. GaitGuard</h1>
              <p className="max-w-5xl mx-auto text-lg md:text-xl text-muted-foreground">
                Traditional gait assessment happens once a week in a clinic. GaitGuard monitors every stride of every session.
              </p>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <LinesPatternCard className="rounded-[1.5rem] shadow-2xl border-destructive/30">
                <LinesPatternCardBody className="p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-2xl font-bold text-destructive">Traditional Rehab</h3>
                    <span className="text-3xl font-black text-destructive">~1 hr/week</span>
                  </div>
                  <div className="space-y-2">
                    {traditionalWorkflowRows.map((row) => (
                      <div key={row.label} className="flex items-center gap-3">
                        <span className={`h-3 w-3 rounded-full shrink-0 ${row.dotClassName}`} />
                        <div className="flex-1 flex items-center justify-between gap-2">
                          <span className="text-sm text-foreground/90">{row.label}</span>
                          {row.barLabel && (
                            <span className="text-xs text-muted-foreground bg-white/5 px-2 py-0.5 rounded">{row.barLabel}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                  <Citation text="(WebPT, 2024; JOSPT, 2024; Princeton Medicine, 2024)." className="!mt-4" />
                </LinesPatternCardBody>
              </LinesPatternCard>

              <LinesPatternCard className="rounded-[1.5rem] shadow-2xl border-primary/30">
                <LinesPatternCardBody className="p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-2xl font-bold text-primary">With GaitGuard</h3>
                    <span className="text-3xl font-black text-primary">Every session</span>
                  </div>
                  <div className="space-y-2">
                    {dispatchWorkflowRows.map((row) => (
                      <div key={row.label} className="flex items-center gap-3">
                        <span className={`h-3 w-3 rounded-full shrink-0 ${row.dotClassName}`} />
                        <span className="text-sm text-foreground/90">{row.label}</span>
                      </div>
                    ))}
                  </div>
                  <Citation text="(Tao et al., 2012; Hochreiter & Schmidhuber, 1997; Winter, 2009)." className="!mt-4" />
                </LinesPatternCardBody>
              </LinesPatternCard>
            </div>

            <LinesPatternCard className="max-w-4xl mx-auto rounded-2xl shadow-xl border-[#7fb0ff]/30">
              <LinesPatternCardBody className="p-5 text-center">
                <p className="text-4xl md:text-5xl font-black text-[#7fb0ff]">167× more data</p>
                <p className="mt-2 text-lg text-muted-foreground">1 clinic hour/week vs. continuous monitoring of every session stride</p>
              </LinesPatternCardBody>
            </LinesPatternCard>
          </div>
        </Section>

        <Section id="eva" className="bg-transparent" contentClassName="max-w-7xl py-6">
          <div className="space-y-5">
            <div className="text-center space-y-2">
              <p className="text-sm font-semibold tracking-[0.24em] uppercase text-primary">EVA — Economic Value Added</p>
              <h1 className="text-4xl md:text-5xl font-bold text-foreground">Unit Economics per Clinic Customer</h1>
            </div>

            <div className="grid gap-4 md:grid-cols-4">
              <div className="rounded-xl border border-primary/25 bg-card/90 p-4 text-center">
                <p className="text-sm text-muted-foreground">Avg. Revenue / Clinic (blended)</p>
                <p className="text-3xl md:text-4xl font-black text-primary mt-1">$2,400</p>
                <p className="text-xs text-muted-foreground mt-1">/year — weighted Clinic/Pro mix</p>
              </div>
              <div className="rounded-xl border border-[#e4b24d]/25 bg-card/90 p-4 text-center">
                <p className="text-sm text-muted-foreground">Est. Gross Margin (SaaS)</p>
                <p className="text-3xl md:text-4xl font-black text-[#e4b24d] mt-1">78%</p>
                <p className="text-xs text-muted-foreground mt-1">ML inference + cloud infra deducted</p>
              </div>
              <div className="rounded-xl border border-[#7fb0ff]/25 bg-card/90 p-4 text-center">
                <p className="text-sm text-muted-foreground">CAC (direct clinic outreach)</p>
                <p className="text-3xl md:text-4xl font-black text-[#7fb0ff] mt-1">$1,800</p>
                <p className="text-xs text-muted-foreground mt-1">6–12 month sales cycle, inbound-assisted</p>
              </div>
              <div className="rounded-xl border border-foreground/15 bg-card/90 p-4 text-center">
                <p className="text-sm text-muted-foreground">Target LTV:CAC</p>
                <p className="text-3xl md:text-4xl font-black text-foreground mt-1">4×</p>
                <p className="text-xs text-muted-foreground mt-1">B2B healthtech benchmark: {'>'}3×</p>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <LinesPatternCard className="rounded-[1.5rem] shadow-xl border-white/10">
                <LinesPatternCardBody className="p-5">
                  <h3 className="text-xl font-bold text-foreground mb-4">EVA per Clinic (3-year horizon)</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center border-b border-border/40 pb-2">
                      <span className="text-muted-foreground">Annual SaaS revenue (blended)</span>
                      <span className="font-semibold text-foreground">$2,400</span>
                    </div>
                    <div className="flex justify-between items-center border-b border-border/40 pb-2">
                      <span className="text-muted-foreground">Gross profit (78%)</span>
                      <span className="font-semibold text-foreground">$1,872</span>
                    </div>
                    <div className="flex justify-between items-center border-b border-border/40 pb-2">
                      <span className="text-muted-foreground">3-year LTV (10% annual churn)</span>
                      <span className="font-semibold text-foreground">$5,040</span>
                    </div>
                    <div className="flex justify-between items-center border-b border-border/40 pb-2">
                      <span className="text-muted-foreground">CAC (direct outreach)</span>
                      <span className="font-semibold text-destructive">-$1,800</span>
                    </div>
                    <div className="flex justify-between items-center border-b border-border/40 pb-2">
                      <span className="text-muted-foreground">Hardware margin per kit</span>
                      <span className="font-semibold text-primary">+$150</span>
                    </div>
                    <div className="flex justify-between items-center pt-1">
                      <span className="font-bold text-foreground">Net EVA / Clinic (3yr)</span>
                      <span className="font-black text-xl text-primary">$3,240</span>
                    </div>
                  </div>
                </LinesPatternCardBody>
              </LinesPatternCard>

              <LinesPatternCard className="rounded-[1.5rem] shadow-xl border-white/10">
                <LinesPatternCardBody className="p-5">
                  <h3 className="text-xl font-bold text-foreground mb-4">Value created vs. traditional gait lab</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center border-b border-border/40 pb-2">
                      <span className="text-muted-foreground">Vicon system (one-time)</span>
                      <span className="font-semibold text-destructive">$12,500+</span>
                    </div>
                    <div className="flex justify-between items-center border-b border-border/40 pb-2">
                      <span className="text-muted-foreground">GaitGuard Pro (annual)</span>
                      <span className="font-semibold text-foreground">$3,588</span>
                    </div>
                    <div className="flex justify-between items-center border-b border-border/40 pb-2">
                      <span className="text-muted-foreground">Clinical sessions replaced (2×/mo × $350)</span>
                      <span className="font-semibold text-primary">$8,400/yr/patient</span>
                    </div>
                    <div className="flex justify-between items-center border-b border-border/40 pb-2">
                      <span className="text-muted-foreground">ACL re-reconstruction cost avoided</span>
                      <span className="font-semibold text-primary">~$30–50K/event</span>
                    </div>
                    <div className="flex justify-between items-center pt-1">
                      <span className="font-bold text-foreground">Customer ROI multiplier</span>
                      <span className="font-black text-xl text-primary">~10–15×</span>
                    </div>
                  </div>
                </LinesPatternCardBody>
              </LinesPatternCard>
            </div>

            <LinesPatternCard className="max-w-6xl mx-auto rounded-2xl shadow-xl border-[#e4b24d]/25">
              <LinesPatternCardBody className="p-5">
                <p className="text-foreground leading-relaxed">
                  <span className="font-bold text-[#e4b24d]">Key risk to EVA:</span> B2B clinic sales cycles are 6–12 months, making early CAC recovery slow. Partnering with orthopedic surgery groups and PT schools as distribution channels can compress CAC and accelerate adoption beyond cold outreach.
                </p>
              </LinesPatternCardBody>
            </LinesPatternCard>
          </div>
        </Section>

        <Section id="clinical" className="bg-transparent">
          <div className="space-y-8">
            <div className="text-center space-y-4">
              <h1 className="text-5xl md:text-7xl font-bold text-foreground">Phase 0 + 1: Calibration</h1>
              <p className="max-w-4xl mx-auto text-xl md:text-2xl text-muted-foreground">
                GaitGuard does not start scoring immediately. It first learns your baseline — then segments every stride automatically.
              </p>
            </div>

            <div className="grid max-w-7xl mx-auto gap-6 md:grid-cols-3">
              {preReconCards.map((card, index) => (
                <motion.div
                  key={card.title}
                  initial={{ opacity: 0, y: 28 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.55, delay: 0.1 * index }}
                >
                  <LinesPatternCard className={`rounded-2xl shadow-xl h-full ${card.borderClassName}`}>
                    <LinesPatternCardBody className="p-8">
                      <h3 className={`text-3xl font-bold mb-5 ${card.accentClassName}`}>{card.title}</h3>
                      <p className="text-foreground text-xl leading-relaxed">{card.text}</p>
                      <Citation text={card.citation} />
                    </LinesPatternCardBody>
                  </LinesPatternCard>
                </motion.div>
              ))}
            </div>

            <LinesPatternCard className="max-w-6xl mx-auto rounded-2xl shadow-2xl border-primary/25">
              <LinesPatternCardBody className="p-8 text-center">
                <p className="text-2xl md:text-3xl font-semibold text-foreground leading-snug">
                  Before any scoring begins, GaitGuard runs a fully automated calibration pass to produce a personalized joint angle baseline and stride library that drives twin generation.
                </p>
                <Citation
                  text={'(Winter, 2009; Madgwick et al., 2011; Tao et al., 2012).'}
                  className="text-center"
                />
              </LinesPatternCardBody>
            </LinesPatternCard>
          </div>
        </Section>

        <Section id="solution" className="bg-transparent" contentClassName="max-w-6xl py-12">
          <div className="space-y-6">
            <div className="text-center space-y-3">
              <h1 className="text-5xl md:text-6xl font-bold text-foreground">GaitGuard Architecture</h1>
              <p className="text-xl md:text-2xl text-muted-foreground font-light max-w-4xl mx-auto">
                Rehab tools give you a weekly summary. GaitGuard corrects you mid-stride.
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-5 max-w-6xl mx-auto">
              {architectureCards.map((card, index) => (
                <motion.div
                  key={card.title}
                  initial={{ opacity: 0, y: 28 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.55, delay: 0.12 * index }}
                >
                  <LinesPatternCard className={`rounded-2xl shadow-xl h-full ${card.borderClassName}`}>
                    <LinesPatternCardBody className="p-6 text-center">
                      <h3 className={`text-2xl font-bold mb-3 ${card.accentClassName}`}>{card.title}</h3>
                      <p className="text-foreground text-lg leading-relaxed">{card.text}</p>
                      <Citation text={card.citation} className="text-center !mt-2" />
                    </LinesPatternCardBody>
                  </LinesPatternCard>
                </motion.div>
              ))}
            </div>

            <LinesPatternCard className="max-w-6xl mx-auto rounded-2xl shadow-2xl border-accent/30">
              <LinesPatternCardBody className="text-center p-7">
                <div className="text-3xl md:text-4xl font-bold text-accent mb-2">
                  All four phases run automatically from one command
                </div>
                <p className="text-xl text-foreground font-semibold mb-1">
                  Hardware, synthetic data, or public dataset replay — the IMUSource pipeline is fully swappable.
                </p>
                <Citation
                  text={'(Hochreiter & Schmidhuber, 1997; Madgwick et al., 2011; Winter, 2009).'}
                  className="text-center !mt-2"
                />
              </LinesPatternCardBody>
            </LinesPatternCard>
          </div>
        </Section>

        <Section id="dashboard" className="bg-transparent" contentClassName="max-w-7xl py-8">
          <div className="space-y-5">
            <div className="text-center space-y-2">
              <h1 className="text-4xl md:text-6xl font-bold text-foreground">Outputs Clinicians and Patients Actually Use</h1>
              <p className="max-w-5xl mx-auto text-lg md:text-xl text-muted-foreground">
                GaitGuard is designed around actionable outputs — not another dead-end score sheet.
              </p>
            </div>

            <div className="grid gap-4 max-w-7xl mx-auto md:grid-cols-2">
              {outputCards.map((card, index) => (
                <motion.div
                  key={card.title}
                  initial={{ opacity: 0, y: 28 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.55, delay: 0.1 * index }}
                >
                  <LinesPatternCard className={`rounded-2xl shadow-xl h-full ${card.borderClassName}`}>
                    <LinesPatternCardBody className="p-5">
                      <h3 className={`text-2xl font-bold mb-2 ${card.accentClassName}`}>{card.title}</h3>
                      <p className="text-foreground text-base leading-relaxed">{card.text}</p>
                      <Citation text={card.citation} className="!mt-2" />
                    </LinesPatternCardBody>
                  </LinesPatternCard>
                </motion.div>
              ))}
            </div>

            <LinesPatternCard className="max-w-6xl mx-auto rounded-2xl shadow-2xl border-secondary/30">
              <LinesPatternCardBody className="p-6 text-center">
                <p className="text-lg md:text-xl font-semibold text-foreground leading-snug">
                  The barrier to a gait assessment drops to zero: strap sensors, walk, get report.
                </p>
                <Citation
                  text={'(APTA Clinical Practice Guidelines, 2022; Winter, 2009).'}
                  className="text-center !mt-2"
                />
              </LinesPatternCardBody>
            </LinesPatternCard>
          </div>
        </Section>

        <Section id="muscle" className="bg-transparent" contentClassName="max-w-7xl py-12">
          <div className="space-y-6">
            <div className="text-center space-y-3">
              <h1 className="text-5xl md:text-6xl font-bold text-foreground">The Haptic Cue = The Contract</h1>
              <p className="max-w-5xl mx-auto text-lg md:text-xl text-muted-foreground">
                GaitGuard closes the loop between deviation detection and real-time behavioral correction — within the same stride.
              </p>
            </div>

            <div className="grid gap-5 max-w-7xl mx-auto md:grid-cols-3">
              {fixLoopCards.map((card, index) => (
                <motion.div
                  key={card.title}
                  initial={{ opacity: 0, y: 28 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.55, delay: 0.1 * index }}
                >
                  <LinesPatternCard className={`rounded-2xl shadow-xl h-full ${card.borderClassName}`}>
                    <LinesPatternCardBody className="p-6">
                      <p className={`text-sm font-semibold tracking-[0.18em] uppercase ${card.accentClassName}`}>{card.badge}</p>
                      <h3 className="mt-3 text-2xl font-bold text-foreground">{card.title}</h3>
                      <p className="mt-3 text-lg leading-relaxed text-muted-foreground">{card.text}</p>
                      <Citation text={card.citation} className="!mt-2" />
                    </LinesPatternCardBody>
                  </LinesPatternCard>
                </motion.div>
              ))}
            </div>

            <LinesPatternCard className="max-w-6xl mx-auto rounded-2xl shadow-2xl border-accent/30">
              <LinesPatternCardBody className="p-6">
                <p className="text-xl md:text-2xl font-semibold text-foreground leading-snug text-center">
                  Each stride carries its GHS, z-score deviation for knee and ankle, and the haptic pattern fired. The session CSV becomes the audit trail: every deviation, every cue, every step — in one file.
                </p>
                <Citation
                  text={'(Perry & Burnfield, 2010; Tao et al., 2012; Winter, 2009).'}
                  className="text-center !mt-2"
                />
              </LinesPatternCardBody>
            </LinesPatternCard>
          </div>
        </Section>
      </div>

    </div>
  );
};

export default Index;
