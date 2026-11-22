import fs from 'node:fs/promises';
import { constants } from 'node:fs';
import { createHash, randomUUID } from 'node:crypto';
import path from 'node:path';
import { exportPages, readDeck } from './deck.mjs';
import { powerPoint } from './pptx.mjs';
import { inspectExport } from './review.mjs';
import { isTextOverflow, repairPhotoPages } from './photo-repair.mjs';

const elapsed = start => Math.round(performance.now() - start);
const deterministic = report => report.issues.filter(issue => issue.source === 'deterministic');
const unresolved = report => deterministic(report).filter(issue => issue.severity === 'blocker' || isTextOverflow(issue));
const writeReport = (file, report) => fs.writeFile(file, JSON.stringify(report, null, 2) + '\n');

async function publish(file, destination) {
  const temp = path.join(path.dirname(destination), '.' + randomUUID() + '.tmp');
  try {
    await fs.copyFile(file, temp, constants.COPYFILE_EXCL);
    await fs.rename(temp, destination);
  } finally {
    await fs.rm(temp, { force: true });
  }
}

export async function deliverPhotography(destination, raw, { backend, backendError }) {
  const start = performance.now();
  const deck = readDeck(raw);
  const output = await fs.mkdtemp(destination + '.review-');
  const reportPath = path.join(output, 'report.json');
  const rounds = [];
  const skipped = [];

  async function render(stage, pages, changes) {
    const start = performance.now();
    const dir = path.join(output, stage);
    const reviewDir = path.join(dir, 'review');
    const pptx = path.join(dir, 'deck.pptx');
    const reportPath = path.join(reviewDir, 'report.json');
    await fs.mkdir(reviewDir, { recursive: true });
    let bytes, exported, report;
    try {
      bytes = await powerPoint(deck, pages);
      await fs.writeFile(pptx, bytes, { flag: 'wx', mode: 0o600 });
      exported = true;
      report = await inspectExport(reviewDir, bytes, deck, { backend, backendError, pages, deterministicOnly: true });
    } catch (error) {
      report = {
        schemaVersion: 1, deckId: deck.id, status: 'preview_unavailable', pages: [], issues: [],
        ...(exported && { pptxSha256: createHash('sha256').update(bytes).digest('hex') }),
        critic: { status: 'not_requested' }, error: error.message, durationMs: elapsed(start),
      };
      await writeReport(reportPath, report);
    }
    const round = {
      stage, changes, durationMs: elapsed(start), pptx: exported ? pptx : null, report: reportPath,
      reviewStatus: report.status, accepted: false, reason: report.error ?? null,
    };
    rounds.push(round);
    return { pages, report, round };
  }

  const initial = await render('initial', exportPages(deck), []);
  let best = initial;
  initial.round.accepted = Boolean(initial.round.pptx);

  // Retry each strategy at most once. Only a measured improvement can replace the current export.
  for (const stage of ['local', 'fallback']) {
    if (best.report.status === 'preview_unavailable' || !best.report.issues.some(isTextOverflow)) break;
    const { pages, changes } = repairPhotoPages(deck, best.pages, best.report.issues, stage);
    if (!changes.length) {
      skipped.push({ stage, reason: 'No applicable text frames fit the available layout space.' });
      continue;
    }
    const candidate = await render(stage, pages, changes);
    if (candidate.report.status === 'preview_unavailable') continue;
    const prior = new Set(deterministic(best.report).map(issue => issue.issueId));
    const added = deterministic(candidate.report).filter(issue => !prior.has(issue.issueId));
    if (added.length) {
      candidate.round.reason = 'New deterministic findings: ' + added.map(issue => issue.issueId).join(', ');
    } else if (unresolved(candidate.report).length >= unresolved(best.report).length) {
      candidate.round.reason = 'The renderer did not clear any additional delivery blockers.';
    } else {
      candidate.round.accepted = true;
      best = candidate;
    }
  }

  const remaining = unresolved(best.report);
  let failureReason = best.report.status === 'preview_unavailable'
    ? best.report.error || 'Preflight could not verify the export.'
    : remaining.length ? 'Unresolved deterministic findings: ' + remaining.map(issue => issue.issueId).join(', ') : null;
  const finalPptx = best.round.pptx
    ? path.join(output, failureReason ? 'draft.pptx' : 'final.pptx') : null;
  if (finalPptx) await fs.copyFile(best.round.pptx, finalPptx, constants.COPYFILE_EXCL);

  let delivery;
  async function saveDelivery() {
    const status = failureReason ? (finalPptx ? 'draft' : 'export_failed') : best.report.status;
    delivery = {
      destination: failureReason ? finalPptx : destination, requestedDestination: destination,
      status, reviewStatus: best.report.status, critic: best.report.critic.status,
      report: reportPath, initialPptx: initial.round.pptx, initialReport: initial.round.report,
      finalPptx, finalReport: best.round.report, repairAttempts: rounds.length - 1,
      durationMs: elapsed(start), failureReason,
    };
    const relative = file => path.relative(output, path.join(path.dirname(best.round.report), file)).split(path.sep).join('/');
    await writeReport(reportPath, {
      ...best.report, ...delivery, critic: best.report.critic, rounds, skipped,
      pages: best.report.pages.map(page => ({ ...page, png: relative(page.png) })),
      ...(best.report.contactSheet && { contactSheet: relative(best.report.contactSheet) }),
      unresolvedIssues: remaining.map(issue => issue.issueId),
    });
  }

  // Write the audit before touching the user's destination. A failed publish leaves the checked copy available.
  await saveDelivery();
  if (!failureReason) {
    try {
      await publish(finalPptx, destination);
    } catch (error) {
      failureReason = 'Could not publish the checked export: ' + error.message;
    }
    await saveDelivery();
  }
  return delivery;
}
