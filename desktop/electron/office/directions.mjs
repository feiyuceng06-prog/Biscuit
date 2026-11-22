// All colors are Biscuit-authored choices. Reference files may select a light or dark
// variant, but never supply color values, font names, or other rendering instructions.
const sans = { latin: 'Arial', cjk: 'Noto Sans CJK SC', fallback: ['Microsoft YaHei', 'PingFang SC', 'sans-serif'] };
const serif = { latin: 'Georgia', cjk: 'Noto Serif CJK SC', fallback: ['Songti SC', 'SimSun', 'serif'] };
const corporate = { ...sans, latin: 'Segoe UI', fallback: ['Arial', ...sans.fallback] };
const mono = { ...sans, latin: 'Courier New', fallback: [...sans.fallback.slice(0, -1), 'monospace'] };
const spacing = (margin, top, gap, gutter, inset) => ({ margin, top, gap, gutter, inset, footer: 501 });
const type = (cover, title, label, body, lineHeight, boldTitle) => ({
  cover, title, label, body, lineHeight, boldTitle,
  display: cover - 8, caption: 13, category: 14, value: 15,
});
const palette = (bg, ink, soft, tint, rule, accent, mutedBar) =>
  ({ bg, ink, soft, tint, rule, accent, mutedBar });

export const directions = {
  editorial: {
    thesis: '用衬线大标题、细分隔线和有节制的图像建立叙事层次。',
    alignment: 'left',
    fonts: { title: serif, body: sans, data: sans },
    typography: type(66, 49, 24, 22, 1.25, false),
    spacing: spacing(60, 45, 25, 28, 13),
    graphics: { motif: 'rule', rule: 1, marker: 'circle', cover: 'tint', imageSide: 'left', imageShare: 0.49, chartSide: 'right', panelFill: false },
    light: palette('FAF6F0', '2F2421', '61524B', 'F0E4DA', 'C7AA9D', '893C43', '997F79'),
    dark: palette('221C20', 'FBF2EB', 'D5C1BB', '392B32', '795763', 'FFB5BA', 'A0808A'),
  },
  minimal: {
    thesis: '让大面积留白、单一重点色和无衬线排版承载信息。',
    alignment: 'center',
    fonts: { title: sans, body: sans, data: sans },
    typography: type(62, 46, 22, 21, 1.3, true),
    spacing: spacing(74, 49, 32, 36, 9),
    graphics: { motif: 'dash', rule: 1, marker: 'circle', cover: 'plain', imageSide: 'right', imageShare: 0.45, chartSide: 'left', panelFill: false },
    light: palette('FCFCFA', '202220', '4F5752', 'EEF1EF', 'CBD3CE', '246252', '789084'),
    dark: palette('19201E', 'F5F7F5', 'C8D2CD', '26312D', '5C7167', 'A9E2C9', '718F83'),
  },
  corporate: {
    thesis: '用清晰的左对齐、深蓝标题和有边界的内容区组织证据与对比。',
    alignment: 'left',
    fonts: { title: corporate, body: corporate, data: corporate },
    typography: type(58, 43, 23, 20, 1.24, true),
    spacing: spacing(54, 40, 22, 22, 17),
    graphics: { motif: 'rail', rule: 2, marker: 'square', cover: 'rail', imageSide: 'right', imageShare: 0.46, chartSide: 'left', panelFill: true },
    light: palette('F7F9FD', '152C48', '465A72', 'E8EEF8', 'AABCD6', '244F96', '7089AE'),
    dark: palette('141E30', 'EDF4FF', 'B7CAE4', '22334F', '526E96', 'A8CCFF', '6F8BB4'),
  },
  technology: {
    thesis: '用高对比配色、精准的线框和等宽数字突出图表与流程。',
    alignment: 'left',
    fonts: { title: sans, body: sans, data: mono },
    typography: { ...type(60, 45, 22, 20, 1.22, true), category: 13, value: 16 },
    spacing: spacing(60, 44, 24, 24, 15),
    graphics: { motif: 'corner', rule: 2, marker: 'square', cover: 'frame', imageSide: 'left', imageShare: 0.48, chartSide: 'left', panelFill: true },
    light: palette('F0F9FC', '102732', '355461', 'DDEDF3', '8FB3C2', '076178', '648A98'),
    dark: palette('101D27', 'EFF8FD', 'B5CBD8', '1B3140', '466B7A', '78DBEF', '648EA0'),
    preferDark: true,
  },
};
