import { newDeck, newSlide, blankItem } from '../../electron/office/deck.mjs';

// A working example. Every run gets fresh IDs so edits belong to the new draft.
export function libraryExample(photo) {
  function page(layout, title, entries, options = {}) {
    return {
      ...newSlide(title, layout),
      generated: true,
      ...options,
      items: entries.map(([label, text, value = 0]) => ({ ...blankItem(), label, text, value })),
    };
  }
  return {
    ...newDeck(),
    theme: 'sand',
    title: '闭馆之后的一小时',
    brief: '向馆务会汇报三个周五的夜读试点，决定下一阶段开放范围。',
    source:
      '虚构教学案例。三个周五 20:00 至 21:00，阅览室分别接待 26、35、48 人次。只提供阅览服务。建议在原班次内开放一层，暂缓增开借还服务。试行四周，每周记录客流和排班，第四周复盘。',
    slides: [
      page('cover', '闭馆之后的\n一小时', [['夜读试点 · 虚构示例', '三个周五的延时开放观察']], {
        image: photo,
        notes: '本演示使用虚构数据，阅览室配图由 AI 生成。',
      }),
      page(
        'chart',
        '连续三个周五，夜读客流逐周上升',
        [
          ['首周', '', 26],
          ['第二周', '', 35],
          ['第三周', '比首周多了 22 人次。三个晚上的记录，还不足以判断长期需求。', 48],
        ],
        { unit: '人次', notes: '虚构示例。口径为每周五 20:00 至 21:00 的入室人次。' },
      ),
      page('comparison', '下一轮，借还服务要一起延时吗？', [
        ['只开阅览室', '沿用现有班次，继续观察同一时段的夜读客流。'],
        ['同时开放借还', '需要另排服务台班次。先登记晚间借还需求，再决定是否增开。'],
      ]),
      page('timeline', '用四个周五验证需求', [
        ['开放前', '公布一层阅览室的延时时段。'],
        ['每周五', '20:00 至 21:00 记录入室人次、借还咨询和实际排班。'],
        ['第四周后', '一起复核客流与排班，再决定是否常态开放。'],
      ]),
      page('conclusion', '先让一层的灯多亮一小时', [
        ['本次决定', '申请再试行四周，周五延时开放一层阅览室。'],
        ['复盘依据', '把四次夜读客流、借还咨询与实际排班放在一起看。'],
      ]),
    ],
  };
}
