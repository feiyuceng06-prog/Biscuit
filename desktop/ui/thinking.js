// The control only commits a discrete level on release, click or keyboard selection.
function createThinkingControl(host, sendMessage) {
  const root = host.attachShadow({ mode: "open" });
  root.append(document.getElementById("thinking-template").content.cloneNode(true));
  const $ = (selector) => root.querySelector(selector);
  const values = ["low", "medium", "high", "xhigh"];
  let status = null;
  let model = "";
  let requested = null;
  const modes = [
    ["日常", "轻松处理日常问题"],
    ["标准", "兼顾响应速度和推理深度"],
    ["深入", "多想一步，适合分析与调试"],
    ["Pro", "深入推演，适合多步任务"],
  ];
  const slider = $(".slider"),
    trigger = $(".trigger"),
    panel = $(".pop");
  const rail = $(".rail");
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const last = modes.length - 1;
  let selected = -1;
  let destination = 0;
  let animation = 0;
  let pointer = null;

  const meteorFrames = [
    { transform: "translate(0,0)", opacity: 0 },
    { offset: 0.16, opacity: "var(--star-light, 1)" },
    { offset: 0.82, opacity: "var(--star-light, 1)" },
    { transform: "translate(calc(100cqw + 50px),15px)", opacity: 0 },
  ];
  const fill = rail.querySelector(".fill");

  const meteorLimit = 10;
  let intensity = 0;
  let impactArmed = true;
  rail.addEventListener("animationend", (event) => {
    if (event.animationName === "pro-impact") rail.classList.remove("pro-impact");
  });
  const stoneSpin = $(".stone").animate(
    [{ transform: "rotate(0turn)" }, { transform: "rotate(1turn)" }],
    { duration: 1000, iterations: Infinity, easing: "linear" },
  );
  for (let i = fill.childElementCount; i < meteorLimit; i++) {
    const star = document.createElement("span");
    star.className = i % 2 ? "meteor far" : "meteor";
    star.style.top = ((i * 7) % 12) - 2 + "px";
    fill.append(star);
  }
  const meteors = [...rail.querySelectorAll(".meteor")];
  const currents = meteors.map((star, i) =>
    star.animate(meteorFrames, {
      duration: 2450 + ((i * 307) % 800),
      delay: -370 - i * 619,
      iterations: Infinity,
      easing: "linear",
    }),
  );
  for (const motion of currents) {
    // Start deep inside the infinite loop so reversing near launch stays seamless.
    motion.currentTime = motion.effect.getTiming().duration * 1000000;
  }
  let flowRate = 1;
  let targetRate = 1;
  let flowFrame = 0;
  let previousTime = 0;
  let lastDragValue = slider.valueAsNumber;
  let direction = 1;

  function activeRate() {
    const multiplier = 0.8 + 3.6 * intensity ** 1.8;
    return direction * multiplier * (pointer === null ? 1 : 2.2);
  }
  function syncFlow() {
    const paused = panel.hidden || document.hidden || reducedMotion.matches;
    if (paused) rail.classList.remove("pro-impact");
    cancelAnimationFrame(flowFrame);
    flowFrame = 0;
    previousTime = 0;
    flowRate = targetRate = activeRate();
    if (paused) stoneSpin.pause();
    else stoneSpin.play();
    for (const motion of currents) {
      if (paused) motion.pause();
      else motion.play();
      motion.updatePlaybackRate(flowRate);
    }
    rail.toggleAttribute("data-reverse", flowRate < 0);
  }
  function easeFlow(time) {
    const elapsed = previousTime ? time - previousTime : 16;
    previousTime = time;
    flowRate += (targetRate - flowRate) * (1 - Math.exp(-elapsed / 75));
    const done = Math.abs(flowRate - targetRate) < 0.015;
    if (done) flowRate = targetRate;
    rail.toggleAttribute("data-reverse", flowRate < 0);
    for (const motion of currents) motion.updatePlaybackRate(flowRate);
    flowFrame = done ? 0 : requestAnimationFrame(easeFlow);
    if (done) previousTime = 0;
  }
  function changeFlow(rate) {
    if (reducedMotion.matches || panel.hidden || document.hidden) return;
    targetRate = rate;
    if (!flowFrame) flowFrame = requestAnimationFrame(easeFlow);
  }
  reducedMotion.addEventListener("change", syncFlow);
  document.addEventListener("visibilitychange", syncFlow);
  syncFlow();

  for (const [index, [label]] of modes.entries()) {
    const button = document.createElement("button");
    button.className = "level";
    button.textContent = label;
    button.onclick = () => commit(index);
    $(".levels").append(button);
  }

  function showLevel(index) {
    if (selected === index) return;
    selected = index;
    const [label, detail] = modes[index];
    slider.setAttribute("aria-valuetext", label);
    $("#name").textContent = label;
    $("#desc").textContent = detail;

    root.querySelectorAll(".level").forEach((button, i) => {
      button.setAttribute("aria-pressed", String(i === index));
    });
  }

  let displayed = slider.valueAsNumber;
  let followFrame = 0;
  let followTime = 0;
  function paint(position, writeInput = true) {
    displayed = position;
    if (writeInput) slider.value = position;
    // The native thumb travels between its two center points, inset by half its width.
    const fraction = position / last;
    // Latch at the end stop. Small motions near the edge shouldn't retrigger recoil.
    if (fraction < 0.86) {
      impactArmed = true;
      rail.classList.remove("pro-impact");
    }
    if (fraction >= 0.995 && impactArmed) {
      impactArmed = false;
      if (!reducedMotion.matches && !panel.hidden && !document.hidden)
        rail.classList.add("pro-impact");
    }
    intensity = fraction;
    stoneSpin.updatePlaybackRate(0.12 + 3.88 * fraction ** 2.2);
    const density = 1 + (meteorLimit - 1) * fraction ** 1.7;
    meteors.forEach((star, i) => {
      star.style.setProperty("--star-light", Math.max(0, Math.min(1, density - i)));
    });
    const air = Math.max(0, (fraction - 0.42) / 0.58);
    const heat = air * air * (3 - 2 * air);
    rail.style.setProperty("--heat", heat);
    rail.style.setProperty("--wake-length", 0.52 + heat * 0.65);
    rail.style.setProperty("--rim-width", 1 + 1.6 * heat);
    changeFlow(activeRate());
    rail.style.setProperty(
      "--cut",
      `calc(${100 * (1 - fraction)}% + ${(2 * fraction - 1) * 15.5}px)`,
    );
  }

  function follow(time) {
    const target = slider.valueAsNumber;
    const elapsed = followTime ? time - followTime : 16;
    followTime = time;
    const response = 6 + 130 * (target / last) ** 2;
    const next = target + (displayed - target) * Math.exp(-elapsed / response);
    const arrived = Math.abs(target - next) < 0.002;
    paint(arrived ? target : next, false);
    showLevel(Math.round(displayed));
    followFrame = arrived ? 0 : requestAnimationFrame(follow);
    if (arrived) followTime = 0;
  }

  function confirmLevel(index) {
    const button = $(".levels").children[index];
    button.classList.add("confirmed");
    button.onanimationend = () => button.classList.remove("confirmed");
  }

  function clearConfirmation() {
    panel.querySelector(".confirmed")?.classList.remove("confirmed");
  }

  function settle(index, animate = true) {
    cancelAnimationFrame(followFrame);
    followFrame = followTime = 0;
    clearConfirmation();
    cancelAnimationFrame(animation);
    destination = index;
    const start = displayed;
    if (!animate || reducedMotion.matches || start === index) {
      paint(index);
      showLevel(index);
      if (animate && !reducedMotion.matches) confirmLevel(index);
      return;
    }
    const began = performance.now();
    const distance = Math.abs(start - index);
    const duration = 96 + 64 * distance + 36 * index;
    function frame(time) {
      const t = Math.min(1, (time - began) / duration);
      const progress = distance > 0.65 ? t * t * (3 - 2 * t) : 1 - (1 - t) ** 3;
      paint(start + (index - start) * progress);
      showLevel(Math.round(displayed));
      if (t < 1) animation = requestAnimationFrame(frame);
      else confirmLevel(index);
    }
    animation = requestAnimationFrame(frame);
  }

  slider.addEventListener("pointerdown", (event) => {
    if (!event.isPrimary || event.button !== 0) return;
    cancelAnimationFrame(animation);
    clearConfirmation();
    rail.classList.add("dragging");
    lastDragValue = slider.valueAsNumber;
    pointer = event.pointerId;
    slider.setPointerCapture(pointer);
  });
  slider.addEventListener("input", () => {
    const position = slider.valueAsNumber;
    if (pointer !== null && position !== lastDragValue) {
      direction = Math.sign(position - lastDragValue);
      changeFlow(activeRate());
      lastDragValue = position;
    }
    if (pointer !== null && !reducedMotion.matches) {
      if (!followFrame) followFrame = requestAnimationFrame(follow);
    } else {
      paint(position);
      showLevel(Math.round(position));
    }
  });
  function finishPointer(event) {
    if (pointer !== event.pointerId) return;
    pointer = null;
    rail.classList.remove("dragging");
    changeFlow(activeRate());
    if (event.type === "pointerup") commit(Math.round(slider.valueAsNumber));
    else reflect();
  }
  slider.addEventListener("pointerup", finishPointer);
  slider.addEventListener("pointercancel", finishPointer);
  slider.addEventListener("lostpointercapture", finishPointer);
  slider.addEventListener("change", () => {
    if (pointer === null && !panel.hidden) commit(Math.round(slider.valueAsNumber));
  });
  slider.addEventListener("keydown", (event) => {
    const base = pointer === null ? destination : Math.round(slider.valueAsNumber);
    const targets = {
      ArrowRight: base + 1,
      ArrowUp: base + 1,
      ArrowLeft: base - 1,
      ArrowDown: base - 1,
      PageUp: base + 1,
      PageDown: base - 1,
      Home: 0,
      End: last,
    };
    if (!(event.key in targets)) return;
    event.preventDefault();
    commit(Math.max(0, Math.min(last, targets[event.key])));
  });

  function currentIndex() {
    if (!status?.enabled) return -1;
    return values.indexOf(status.effort);
  }
  function caption() {
    const index = currentIndex();
    if (!status) return "—";
    if (!status.enabled) return "已关闭";
    return index >= 0 ? modes[index][0] : status.effort || "模型默认";
  }
  function reflect() {
    const index = currentIndex();
    settle(status?.effort === "max" && status.enabled ? last : Math.max(index, 0), false);
    if (index < 0) {
      selected = -1;
      $("#name").textContent = caption();
      $("#desc").textContent = "选择档位以调整下一条消息的思考强度";
      slider.setAttribute("aria-valuetext", caption());
      for (const button of $(".levels").children) button.setAttribute("aria-pressed", "false");
    }
    trigger.querySelector("b").textContent = caption();
  }
  function commit(index) {
    if (trigger.disabled || !status) return;
    const level = values[index];
    if (level !== (requested ?? (status.enabled && status.effort))) {
      if (!sendMessage({ op: "thinking_level", model, level })) return;
      requested = level;
    }
    settle(index);
  }
  function toggle(open) {
    if (open === !panel.hidden) return;
    panel.hidden = !open;
    trigger.setAttribute("aria-expanded", String(open));
    if (open) {
      positionPanel();
      slider.focus();
    } else {
      pointer = null;
      rail.classList.remove("dragging");
      reflect();
    }
    syncFlow();
  }
  function positionPanel() {
    if (panel.hidden) return;
    const right = trigger.getBoundingClientRect().right;
    panel.style.setProperty("--offset", Math.min(0, right - panel.offsetWidth - 12) + "px");
  }
  window.addEventListener("resize", positionPanel);
  trigger.onclick = () => toggle(panel.hidden);
  const restore = $(".restore");
  restore.onclick = () => {
    slider.focus();
    if (sendMessage({ op: "thinking_level", model, level: "default" })) requested = "default";
  };
  document.addEventListener("pointerdown", (e) => {
    if (!e.composedPath().includes(host)) toggle(false);
  });
  root.addEventListener("focusout", (e) => {
    if (!root.contains(e.relatedTarget)) toggle(false);
  });
  root.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) {
      e.stopPropagation();
      e.preventDefault();
      trigger.focus();
      toggle(false);
    }
  });
  return function update(s = {}) {
    const next = s.ready ? s.thinking : null;
    const changed =
      model !== s.name || status?.effort !== next?.effort || status?.enabled !== next?.enabled;
    if (!next || model !== s.name) requested = null;
    model = s.name || "";
    status = next;
    trigger.disabled = !next || !!s.busy;
    trigger.title = !next
      ? "连接模型后可调整思考强度"
      : s.busy
        ? "本轮结束后可调整"
        : "调整思考强度";
    if (trigger.disabled) toggle(false);
    restore.hidden = !next?.overridden;
    const acknowledged = next && requested === next.effort && next.enabled;
    if (acknowledged || (requested === "default" && !next?.overridden)) requested = null;
    if (changed) {
      trigger.querySelector("b").textContent = caption();
      if (panel.hidden || (!requested && !acknowledged)) reflect();
    }
  };
}
