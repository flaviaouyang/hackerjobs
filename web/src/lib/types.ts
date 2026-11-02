// Shapes of the files written by `hackerjobs export` (web/public/data/).

export type Kind = 'hiring' | 'seeking';
export type Remote = 'remote' | 'hybrid' | 'onsite';
export type PayPeriod = 'year' | 'month' | 'day' | 'hour';
export type PostType = 'job_ad' | 'job_seeker' | 'other';

export interface Pay {
  min: number;
  max: number;
  currency: string | null;
  period: PayPeriod | null;
}

export interface Money {
  amount: number;
  currency: string | null;
}

export interface Role {
  title: string;
  pay: Pay | null;
  locations: string[];
  apply_url: string | null;
  seniority: string | null;
  category: string;
}

export interface HiringFields {
  post_type: PostType | null;
  role_categories: string[];
  company: string | null;
  company_website: string | null;
  company_description: string | null;
  industries: string[];
  company_stage: string | null;
  funding: Money | null;
  valuation: Money | null;
  investors: string[];
  team_size: string | null;
  founded_year: number | null;
  roles: Role[];
  locations: string[];
  remote: Remote | null;
  employment_types: string[];
  pay: Pay | null;
  technologies: string[];
  min_experience_years: number | null;
  languages: string[];
  work_authorization: string | null;
  security_clearance: string | null;
  timezone: string | null;
  hours: string | null;
  education: string | null;
  equity: boolean | null;
  equity_details: string | null;
  benefits: string[];
  visa_sponsorship: boolean | null;
  relocation_support: boolean | null;
  interview_process: string | null;
  contact: string | null;
  application_instructions: string | null;
  applications_closed: boolean | null;
  seniority: string[];
}

export interface SeekingFields {
  post_type: PostType | null;
  roles: string[];
  role_categories: string[];
  locations: string[];
  remote: Remote | null;
  willing_to_relocate: boolean | null;
  timezone: string | null;
  employment_types: string[];
  pay: Pay | null;
  experience_years: number | null;
  work_authorization: string | null;
  availability: string | null;
  languages: string[];
  education: string | null;
  interests: string[];
  technologies: string[];
  contact: string | null;
  website: string | null;
  linkedin: string | null;
  github: string | null;
  resume_url: string | null;
  seniority: string[];
}

export interface HistoryEntry {
  month: string;
  id: number;
  roles: number;
}

interface PostBase {
  id: number;
  author: string;
  posted_at: number;
  html: string;
  key: string | null;
  new: boolean;
  repost_of: number | null;
  history: HistoryEntry[];
}

export interface HiringPost extends PostBase {
  fields: HiringFields;
}

export interface SeekingPost extends PostBase {
  fields: SeekingFields;
}

export type Post = HiringPost | SeekingPost;

export interface Rates {
  date: string;
  cad_per_unit: Record<string, number>;
}

export interface Index {
  generated_at: string;
  months: Record<string, Partial<Record<Kind, number>>>;
  rates: Rates;
}
