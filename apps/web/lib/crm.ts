// Shared types + helpers for the Contacts (CRM) module.
import { api } from "@/lib/api";
import { tenantId } from "@/lib/groundwork";

export const crm = <T,>(path: string, init: RequestInit = {}) =>
  api<T>(path, init, tenantId() ?? undefined);

export type Contact = {
  id: string;
  name: string;
  company_id: string | null;
  company_name: string | null;
  job_title: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  address: string | null;
  notes: string | null;
  tags: string[];
  project_ids: string[];
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

export type Company = {
  id: string;
  name: string;
  website: string | null;
  email: string | null;
  phone: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  postcode: string | null;
  notes: string | null;
  contact_count: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
};

/** Payload shared by contact create and patch forms. */
export type ContactForm = {
  name: string;
  company_id: string | null;
  job_title: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  address: string | null;
  notes: string | null;
  tags: string[];
};

export type CompanyForm = {
  name: string;
  website: string | null;
  email: string | null;
  phone: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  postcode: string | null;
  notes: string | null;
};

export function companyAddress(c: Company): string {
  return [c.address_line1, c.address_line2, c.city, c.postcode].filter(Boolean).join(", ");
}
