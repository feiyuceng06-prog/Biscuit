// Keep heavy inspection out of the Electron main process and off the save path by default.
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import os from 'node:os';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { composition, readDeck } from './deck.mjs';

export function reviewManifest(raw) {
  const deck = readDeck(raw);
  return {
    deckId: deck.id, brief: deck.brief,
    ...(deck.design && { design: {
      direction: deck.design.direction,
      rhythm: deck.design.rhythm,
    } }),
    slides: deck.slides.map((slide, i) => ({
      slideId: slide.id, layout: slide.layout,
      objects: composition(slide, i + 1, deck.slides.length, deck.theme, deck.design).map(({data, ...o}, j) => ({
        ...o, id: o.field || o.type + '-' + (j + 1),
      })),
    })),
  };
}

export async function reviewExport(destination, bytes, deck, backend) {
  const work = await fs.mkdtemp(path.join(os.tmpdir(), 'biscuit-ppt-'));
  try {
    const output = await fs.mkdtemp(destination + '.review-');
    await fs.writeFile(path.join(work, 'deck.pptx'), bytes);
    await fs.writeFile(path.join(work, 'manifest.json'), JSON.stringify(reviewManifest(deck)));
    const reportPath = path.join(output, 'report.json');
    const pptxSha256 = createHash('sha256').update(bytes).digest('hex');
    let processFailure;
    try {
      await promisify(execFile)(backend.command, [...backend.args, '--presentation-review', work, output],
        { windowsHide: true, timeout: 600000, env: { ...process.env, PYTHONUTF8: '1' } });
    } catch (error) {
      processFailure = 'Review process failed: ' + (error.code || error.signal || 'unknown');
    }
    let report;
    try {
      // A timeout during model review may leave a complete local preflight report.
      report = JSON.parse(await fs.readFile(reportPath, 'utf8'));
      if (report?.schemaVersion !== 1 || report.deckId !== deck.id || report.pptxSha256 !== pptxSha256
        || !['preview_unavailable', 'checked', 'needs_review', 'blocked'].includes(report.status)
        || !['not_requested', 'unavailable', 'checked'].includes(report.critic?.status)
        || !Array.isArray(report.pages) || !Array.isArray(report.issues)
        || (report.status !== 'preview_unavailable' && (report.pages.length !== deck.slides.length
          || report.pages.some((page, index) => page?.slideId !== deck.slides[index].id)))) {
        throw new Error('Invalid review report');
      }
    } catch {
      report = { schemaVersion: 1, deckId: deck.id, status: 'preview_unavailable',
        pptxSha256, pages: [], issues: [], critic: { status: 'unavailable' },
        error: processFailure || 'Review process did not produce a valid report.' };
      await fs.writeFile(reportPath, JSON.stringify(report, null, 2));
    }
    return { destination, status: report.status, critic: report.critic.status, report: reportPath };
  } finally {
    await fs.rm(work, { recursive: true, force: true });
  }
}
