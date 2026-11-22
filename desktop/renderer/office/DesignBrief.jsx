import React, { useEffect, useState } from 'react';
import { planDesign } from '../../electron/office/director.mjs';

const directions = { auto: '自动选择', editorial: '编辑叙事', minimal: '极简', corporate: '企业汇报', technology: '技术说明' };

export function DesignBrief({ deck, commit, onError, disabled }) {
  const [preferences, setPreferences] = useState(deck.design?.preferences || {});
  const [loading, setLoading] = useState(false);
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
      commit({ ...deck, design: planDesign(deck, preferences) });
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
        <div className="office-actions">
          <button type="button" onClick={reference}>{loading ? '分析中…' : '分析参考 PPTX'}</button>
          {preferences.reference && <button type="button" onClick={() => setPreferences(({ reference, ...rest }) => rest)}>移除参考</button>}
        </div>
        {preferences.reference && <small>{preferences.reference.name} · {preferences.reference.slideCount} 页</small>}
        <button type="button" className="office-primary" onClick={apply}>应用设计方案</button>
        {deck.design && <p>{deck.design.rationale}</p>}
      </fieldset>
    </details>
  );
}
