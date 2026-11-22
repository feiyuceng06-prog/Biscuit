import React, { useEffect, useState } from 'react';
import { planDesign } from '../../electron/office/director.mjs';
import { hasPhotos } from '../../electron/office/photos.mjs';

const directions = { auto: '自动选择', photography: '摄影集', editorial: '编辑叙事', minimal: '极简', corporate: '企业汇报', technology: '技术说明' };

export function DesignBrief({ deck, slideId, commit, onError, disabled }) {
  const [preferences, setPreferences] = useState(deck.design?.preferences || {});
  const [usePlanner, setUsePlanner] = useState(deck.design?.version !== 1);
  useEffect(() => { setUsePlanner(deck.design?.version !== 1); }, [deck.design?.version]);
  const [loading, setLoading] = useState(false);
  const pagePlan = deck.design?.slidePlans?.find(page => page.slideId === slideId);
  const count = pagePlan?.assetStrategy.photoCount;
  const saved = JSON.stringify(deck.design?.preferences || {});
  useEffect(() => { setPreferences(JSON.parse(saved)); }, [saved]);
  function update(field, value) {
    setPreferences(current => ({ ...current, [field]: value }));
  }
  async function reference() {
    setLoading(true);
    try {
      const profile = await window.feiyuDesktop.core.invoke('presentation_reference');
      if (profile) update('reference', profile);
    } catch (error) {
      onError(error.message);
    } finally {
      setLoading(false);
    }
  }
  function apply() {
    try {
      commit({ ...deck, design: planDesign(deck, preferences, { visualPlanner: usePlanner }) });
    } catch (error) {
      onError(error.message);
    }
  }
  return (
    <details className="office-director">
      <summary>设计方案{deck.design ? ' · ' + directions[deck.design.direction] : ''}</summary>
      <fieldset disabled={disabled || loading}>
        <label>受众<input maxLength={120} value={preferences.audience || ''}
          placeholder="例如：项目负责人" onChange={e => update('audience', e.target.value)} /></label>
        <label>使用场景<input maxLength={120} value={preferences.setting || ''}
          placeholder="例如：技术评审会" onChange={e => update('setting', e.target.value)} /></label>
        <label>品牌强调色（可选）<input maxLength={7} value={preferences.brandAccent || ''}
          placeholder="#24549B" onChange={e => update('brandAccent', e.target.value)} /></label>
        <label>视觉方向<select value={preferences.direction || 'auto'} onChange={e => update('direction', e.target.value)}>
          {Object.entries(directions).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select></label>
        <label className="office-planner-toggle"><input type="checkbox"
          checked={usePlanner || preferences.direction === 'photography' || hasPhotos(deck)}
          disabled={preferences.direction === 'photography' || hasPhotos(deck)}
          onChange={e => setUsePlanner(e.target.checked)} />根据每页内容规划构图</label>
        <div className="office-actions">
          <button type="button" onClick={reference}>{loading ? '分析中…' : '分析参考 PPTX'}</button>
          {preferences.reference && <button type="button" onClick={() => setPreferences(({ reference, ...rest }) => rest)}>移除参考</button>}
        </div>
        {preferences.reference && <small>{preferences.reference.name} · {preferences.reference.slideCount} 页</small>}
        <button type="button" className="office-primary" onClick={apply}>应用设计方案</button>
        {deck.design && <p>{deck.design.rationale}</p>}
      </fieldset>
      {pagePlan && <section className="office-page-plan" aria-label="本页构图">
        <strong>本页构图</strong>
        <span>{pagePlan.selectionReason}</span>
        {count && count.requested !== count.actual && <small>制作要求为 {count.requested} 张照片，本页已导入 {count.actual} 张。</small>}
        {pagePlan.contentEditProposal && <small>此页内容较密，可手动拆页。已保留全部原文。</small>}
      </section>}
    </details>
  );
}
