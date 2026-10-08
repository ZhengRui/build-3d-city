// The viewer's menu: places (areas and landmarks), display settings and controls help, in a compact,
// collapsible panel. Built on the markup in index.html; main.js passes in what the menu can change and the
// city (city.js: the sun's latitude and season, the time shortcuts, the localStorage prefix, what is on).
// Per-browser conveniences (collapsed state, open sections, trackpad mode) are kept in localStorage;
// URL parameters (?ao=0, ?trees=0, ?markings=0, ?waves=0, ?traffic=0, ?roofs=0, ?glow=0, ?time=21) still win for the session.
const { sunAt } = await import(`./city.js${new URL(import.meta.url).search}`);

const clock = (h) => `${Math.floor(h)}:${String(Math.round((h % 1) * 60) % 60).padStart(2, '0')}`;

export function createMenu(api) {
  const { views, goTo, settings, invalidate, setSun, trees, lightShadows, setReflections, hasMarkings, city } = api;
  const { latitude } = city.location, { declination } = city.sun;
  const store = {
    get(k, d) { try { const v = localStorage.getItem(`${city.storagePrefix}.${k}`); return v === null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem(`${city.storagePrefix}.${k}`, JSON.stringify(v)); } catch { /* private mode */ } },
  };
  const $ = (id) => document.getElementById(id);
  const menu = $('menu');

  // collapse the whole panel to its title bar
  const setCollapsed = (c) => { menu.classList.toggle('collapsed', c); $('collapse').setAttribute('aria-expanded', String(!c)); store.set('collapsed', c); };
  $('collapse').onclick = () => setCollapsed(!menu.classList.contains('collapsed'));
  setCollapsed(store.get('collapsed', true));   // folded at the start (the user, 9 Oct): the city first
  for (const d of menu.querySelectorAll('details')) {
    d.open = store.get(`open.${d.id}`, d.open);
    d.addEventListener('toggle', () => store.set(`open.${d.id}`, d.open));
  }

  // the credit line's "About" link opens the menu on its About section
  $('attribution').addEventListener('click', (e) => {
    if (e.target.closest?.('a')?.getAttribute('href') !== '#about') return;
    e.preventDefault();
    setCollapsed(false);
    $('sec-about').open = true;
    $('sec-about').scrollIntoView({ block: 'nearest' });
  });

  // places: one chip per view, grouped; the last one chosen is highlighted
  const places = $('places');
  const groups = {};
  for (const v of views) {
    const g = v.group ?? 'Places';
    if (!groups[g]) {
      const h = document.createElement('div');
      h.className = 'group';
      h.textContent = g;
      const row = document.createElement('div');
      row.className = 'chips';
      places.append(h, row);
      groups[g] = row;
    }
    const b = document.createElement('button');
    b.className = 'chip';
    b.textContent = v.name;
    b.onclick = () => {
      places.querySelector('.chip.active')?.classList.remove('active');
      b.classList.add('active');
      goTo(v);
      // a dusk or night preset ([views.areas]' hour) moves the time there, as the time shortcuts do
      if (v.time !== undefined) { time.value = v.time; jump = true; time.dispatchEvent(new Event('input')); jump = false; }
    };
    groups[g].append(b);
  }

  // on/off switches
  const toggle = (id, initial, apply) => {
    const b = $(id);
    const set = (on) => { b.setAttribute('aria-pressed', String(on)); apply(on); };
    b.onclick = () => set(b.getAttribute('aria-pressed') !== 'true');
    set(initial);
  };
  toggle('t-trees', trees.group.visible, (on) => {
    trees.group.visible = on;
    if (api.groundTrees) api.groundTrees.value = on ? 1 : 0;   // the park ground paints crowns when trees are off
    invalidate({ shadows: true });
  });
  $('t-rooftops').hidden = !api.rooftops;
  if (api.rooftops) {
    toggle('t-rooftops', settings.rooftops, (on) => {
      settings.rooftops = api.rooftops.group.visible = on;
      invalidate({ shadows: true });
    });
  }
  // (main.js setShadows: castShadow left on, the shadows' intensity and pass switched instead; see there)
  if (api.setShadows) toggle('t-shadows', api.shadowsOn(), (on) => api.setShadows(on));
  else toggle('t-shadows', lightShadows.castShadow, (on) => { lightShadows.castShadow = on; invalidate({ shadows: true }); });
  toggle('t-ao', settings.ao, (on) => { settings.ao = on; invalidate(); });
  $('t-markings').hidden = !hasMarkings;
  toggle('t-markings', settings.markings, (on) => { settings.markings = on; invalidate(); });
  toggle('t-mirror', settings.mirror, (on) => api.setMirror(on));
  toggle('t-waves', settings.waves, (on) => { settings.waves = on; invalidate(); });
  toggle('t-traffic', settings.traffic, (on) => api.setTraffic(on));
  // the real street lamps (lamps.js; drawn only after dark) and the towns beyond the districts (06e_masses)
  $('t-lamps').hidden = !api.lamps;
  if (api.lamps) toggle('t-lamps', api.lamps.enabled, (on) => { api.lamps.setEnabled(on); invalidate(); });
  $('t-masses').hidden = !api.hasMasses;
  if (api.hasMasses) toggle('t-masses', settings.masses, (on) => { settings.masses = on; invalidate(); });
  // a city's own tooltips for its switches (city.json switchTitles: { masses: '...', lamps: '...' }), where the
  // generic text would be wrong for its data (Berlin's towns are the Umweltatlas's footprints, not OSM's)
  for (const [k, t] of Object.entries(city.switchTitles ?? {})) if ($(`t-${k}`)) $(`t-${k}`).title = t;
  toggle('t-glow', settings.glow, (on) => { settings.glow = on; invalidate(); });
  toggle('t-stats', store.get('stats', city.features.stats), (on) => { $('stats').hidden = !on; store.set('stats', on); });
  toggle('t-trackpad', store.get('trackpad', true), (on) => {   // on at the start everywhere (the user, 9 Oct)
    settings.trackpad = on;
    store.set('trackpad', on);
    $('help-wheel').textContent = on
      ? 'Two-finger scroll rotates and tilts, pinch zooms, ⇧ + scroll pans.'
      : 'Scroll wheel zooms.';
  });

  // sliders: time of day, haze, glass and water reflections
  const slider = (id, fmt, apply) => {
    const input = $(id), out = $(`${id}-out`);
    const update = () => { out.textContent = fmt(Number(input.value)); apply(Number(input.value)); };
    input.addEventListener('input', update);
    update();
  };
  // time of day over the whole day (local solar time, or clock time with city.time.utcOffset: in Shenzhen in
  // early November sunset is about 17:45 solar time,
  // dark from about 18:35); ?time=21 starts at that hour, else the city's start. The shortcuts jump to an
  // afternoon, the blue hour and the night (city.time.presets)
  const time = $('s-time'), tod = $('tod');
  // the day shown and the clock's zone beside the label: "Time · 10 Oct, EDT"
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const [mm, dd] = (city.sun.date ?? '').split('-').map(Number);
  const when = [mm ? `${dd} ${MONTHS[mm - 1]}` : null, city.time.zone ?? (city.time.utcOffset === null ? 'solar time' : null)]
    .filter(Boolean).join(', ');
  if (when) document.querySelector('label[for="s-time"]').innerHTML = `Time <small>${when}</small>`;
  const TIMES = city.time.presets;
  time.value = settings.time !== undefined ? settings.time : city.time.start;
  for (const [name, h] of Object.entries(TIMES)) {
    const b = document.createElement('button');
    b.textContent = name;
    b.onclick = () => { time.value = h; jump = true; time.dispatchEvent(new Event('input')); jump = false; };
    tod.append(b);
  }
  let jump = false;                  // (a shortcut, not a drag: drawn settled at once)
  slider('s-time', clock, (h) => {
    const s = sunAt(h, latitude, declination, city.time.solarShift);
    setSun(s.azimuth, s.elevation, h, { jump });
    for (const b of tod.children) b.setAttribute('aria-pressed', String(Math.abs(TIMES[b.textContent] - h) < 0.01));
  });
  $('s-haze').value = city.sliders.haze;
  $('s-reflect').value = city.sliders.reflections;
  slider('s-haze', (k) => `${Math.round(k * 100)}%`, (k) => { settings.haze = k; invalidate(); });
  slider('s-reflect', (k) => `${Math.round(k * 100)}%`, (k) => setReflections(k));

  // resolution: device pixels per CSS pixel, offered up to what the screen has
  const res = $('res');
  const choices = [1, 1.5, 2].filter((r) => r <= Math.max(1, devicePixelRatio) + 0.01);
  const movingCap = settings.movingResolution;      // (the city's, or ?moving=: the picked resolution never raises it)
  const pickRes = (r) => {
    settings.resolution = r;
    settings.movingResolution = Math.min(r, movingCap);
    for (const b of res.children) b.setAttribute('aria-pressed', String(Number(b.dataset.r) === r));
    store.set('resolution', r);
    invalidate();
  };
  for (const r of choices) {
    const b = document.createElement('button');
    b.dataset.r = r;
    b.textContent = `${r}×`;
    b.onclick = () => pickRes(r);
    res.append(b);
  }
  const saved = store.get('resolution', settings.resolution);
  pickRes(choices.includes(saved) ? saved : choices[choices.length - 1]);
}
