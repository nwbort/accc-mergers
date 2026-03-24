import fs from 'node:fs';
import path from 'node:path';

const DATA_DIR = path.resolve('public/data');

function readJson(filePath) {
  const fullPath = path.join(DATA_DIR, filePath);
  if (!fs.existsSync(fullPath)) return null;
  return JSON.parse(fs.readFileSync(fullPath, 'utf-8'));
}

export function getStats() {
  return readJson('stats.json');
}

export function getUpcomingEvents() {
  return readJson('upcoming-events.json');
}

export function getCommentary() {
  return readJson('commentary.json');
}

export function getDigest() {
  return readJson('digest.json');
}

export function getAnalysis() {
  return readJson('analysis.json');
}

export function getIndustries() {
  return readJson('industries.json');
}

export function getIndustryDetail(code) {
  return readJson(`industries/${code}.json`);
}

export function getMergerDetail(id) {
  return readJson(`mergers/${id}.json`);
}

export function getMergersListMeta() {
  return readJson('mergers/list-meta.json');
}

export function getMergersListPage(page) {
  return readJson(`mergers/list-page-${page}.json`);
}

export function getAllMergers() {
  const meta = getMergersListMeta();
  if (!meta) return [];
  const allMergers = [];
  for (let i = 1; i <= meta.total_pages; i++) {
    const page = getMergersListPage(i);
    if (page && page.mergers) {
      allMergers.push(...page.mergers);
    }
  }
  return allMergers;
}

export function getTimelineMeta() {
  return readJson('timeline-meta.json');
}

export function getTimelinePage(page) {
  return readJson(`timeline-page-${page}.json`);
}

export function getAllTimelineEvents() {
  const meta = getTimelineMeta();
  if (!meta) return [];
  const allEvents = [];
  for (let i = 1; i <= meta.total_pages; i++) {
    const page = getTimelinePage(i);
    if (page && page.events) {
      allEvents.push(...page.events);
    }
  }
  // Reverse so newest events are first
  return allEvents.reverse();
}

export function getAllMergerIds() {
  const mergers = getAllMergers();
  return mergers.map(m => m.merger_id);
}

export function getAllIndustryCodes() {
  const data = getIndustries();
  if (!data || !data.industries) return [];
  return data.industries.map(i => i.code);
}
