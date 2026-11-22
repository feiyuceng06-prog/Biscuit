// These original, text-only design studies contain no slide files or third-party assets.
const study = (id, direction, title, layouts, topics, density, lesson) => ({
  id, direction, title, layouts, topics, density,
  source: 'builtin',
  owner: 'Biscuit project',
  rights: 'Original text-only design study authored for Biscuit.',
  allowedLessons: [lesson],
  prohibitedReuse: ['slide text', 'imagery', 'logos', 'template or geometry'],
  legibility: density === 'dense' ? 2 : 3,
  editability: 3,
});

const library = [
  study('photography-opening', 'photography', '摄影集开篇', ['cover'], ['story', 'launch'], 'sparse', '用居中的照片组串起开篇叙事。'),
  study('photography-work', 'photography', '摄影作品', ['image'], ['story', 'launch'], 'balanced', '为作品留出连续的展示空间，图注与图片独立。'),
  study('photography-essay', 'photography', '摄影说明', ['conclusion', 'comparison', 'chart', 'timeline'], ['story', 'teaching'], 'balanced', '在独立的文字区保留完整说明。'),
  study('editorial-opening', 'editorial', '长文叙事开篇', ['cover', 'conclusion'], ['story', 'teaching'], 'sparse', '用大标题和细线建立叙事层级。'),
  study('editorial-feature', 'editorial', '图文专题', ['image', 'timeline'], ['story', 'teaching'], 'balanced', '用留白将图片和图旁说明分开。'),
  study('editorial-evidence', 'editorial', '叙事中的证据', ['chart', 'comparison'], ['report', 'story'], 'balanced', '给事实标签留出空间，用细线组织证据。'),
  study('editorial-close-reading', 'editorial', '课堂细读', ['image', 'comparison', 'conclusion'], ['teaching'], 'dense', '让长说明沿稳定的左边线排列，并保留每段的小标题。'),
  study('minimal-opening', 'minimal', '留白开场', ['cover', 'conclusion'], ['launch', 'teaching'], 'sparse', '用留白集中注意力，控制装饰范围。'),
  study('minimal-feature', 'minimal', '简洁产品介绍', ['image', 'comparison'], ['launch', 'story'], 'balanced', '让正文和图片拥有清楚的边界。'),
  study('minimal-evidence', 'minimal', '简洁证据页', ['chart', 'timeline'], ['report', 'teaching'], 'balanced', '直接标记数值，用简单的基线维持阅读顺序。'),
  study('minimal-keynote', 'minimal', '发布演示', ['cover', 'image', 'timeline'], ['launch'], 'sparse', '用较宽的边距和一处强调标记聚拢视线。'),
  study('corporate-briefing', 'corporate', '经营简报', ['cover', 'conclusion'], ['report', 'investor'], 'balanced', '保持稳定的标题与页脚位置，便于浏览。'),
  study('corporate-evidence', 'corporate', '指标与对照', ['chart', 'comparison'], ['report', 'investor'], 'dense', '为证据安排一致的横向空间，保留可编辑图表。'),
  study('corporate-delivery', 'corporate', '交付进展', ['timeline', 'image'], ['report', 'launch'], 'balanced', '让里程碑标记和配图使用同一套强调色。'),
  study('corporate-investment', 'corporate', '投资简报', ['cover', 'conclusion', 'chart', 'comparison'], ['investor'], 'balanced', '将核心指标留在显眼的位置，旁边紧跟解释。'),
  study('technology-opening', 'technology', '技术发布', ['cover', 'conclusion'], ['technology', 'launch'], 'sparse', '用框角和单一亮色建立视觉识别。'),
  study('technology-evidence', 'technology', '产品系统指标', ['chart', 'comparison'], ['technology', 'report'], 'dense', '用对齐的数值和高对比标签帮助扫描数据。'),
  study('technology-sequence', 'technology', '过程与实例', ['timeline', 'image'], ['technology', 'teaching'], 'balanced', '用规则的节点和细线表示时间顺序。'),
  study('technology-demo', 'technology', '产品功能演示', ['cover', 'chart', 'image'], ['launch'], 'balanced', '为产品画面和数字分别留出清晰的区域。'),
];

const densityRank = { sparse: 0, balanced: 1, dense: 2 };

export function selectReference({ layout, direction, topics, density }) {
  const score = (entry) => {
    const capacityGap = densityRank[entry.density] - densityRank[density];
    const topicMatch = entry.topics.filter((topic) => topics.includes(topic)).length;
    return 4 * topicMatch + entry.legibility + entry.editability
      - Math.abs(capacityGap) * (capacityGap < 0 ? 4 : 2);
  };
  return library
    .filter((entry) => entry.layouts.includes(layout))
    .sort((a, b) => Number(b.direction === direction) - Number(a.direction === direction)
      || score(b) - score(a) || (a.id < b.id ? -1 : 1))[0];
}
