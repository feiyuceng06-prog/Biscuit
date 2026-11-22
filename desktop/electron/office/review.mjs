// Keep heavy inspection out of the Electron main process and off the save path by default.
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import os from 'node:os';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { composition } from './deck.mjs';

export function reviewManifest(deck) {
  return {
    deckId: deck.id, brief: deck.brief,
    slides: deck.slides.map((slide, i) => ({
      slideId: slide.id, layout: slide.layout,
      objects: composition(slide, i + 1, deck.slides.length, deck.theme).map(({data, ...o}, j) => ({
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
    try {
      await promisify(execFile)(backend.command, [...backend.args, '--presentation-review', work, output],
        { windowsHide: true, timeout: 600000, env: { ...process.env, PYTHONUTF8: '1' } });
    } catch (error) {
      // A timeout during model review may already have a complete local preflight report.
      const fallback = { schemaVersion: 1, deckId: deck.id, status: 'preview_unavailable',
        pptxSha256: createHash('sha256').update(bytes).digest('hex'), pages: [], issues: [],
        critic: { status: 'unavailable' }, error: 'Review process failed: ' + (error.code || error.signal || 'unknown') };
      try {
        await fs.writeFile(reportPath, JSON.stringify(fallback, null, 2), { flag: 'wx' });
      } catch (writeError) {
        if (writeError.code !== 'EEXIST') throw writeError;
      }
    }
    const report = JSON.parse(await fs.readFile(reportPath, 'utf8'));
    return { destination, status: report.status, critic: report.critic.status, report: reportPath };
  } finally {
    await fs.rm(work, { recursive: true, force: true });
  }
}
