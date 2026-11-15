import { springCss, springs } from '@usefluid/motion';

const spring = springCss(springs.soft);
document.documentElement.style.setProperty('--voyage-spring', spring.easing);
document.documentElement.style.setProperty('--voyage-duration', `${spring.duration}ms`);
