<template>
  <div class="login-page" :class="`theme-${theme}`">
    <div class="theme-switch">
      <button
        class="theme-btn"
        :class="{ active: theme === 'dark' }"
        type="button"
        @click="setTheme('dark')"
      >
        深色
      </button>
      <button
        class="theme-btn"
        :class="{ active: theme === 'light' }"
        type="button"
        @click="setTheme('light')"
      >
        浅色
      </button>
    </div>

    <div class="bg-layer" aria-hidden="true">
      <div class="mesh mesh-a" />
      <div class="mesh mesh-b" />
      <div class="mesh mesh-c" />
      <div class="grain" />
      <div class="grid" />
      <div class="light-beam" />
    </div>

    <section class="hero-copy" aria-hidden="true">
      <div class="pill">GLOBAL QUANT DESK</div>
      <h2>Next-Gen Trading<br />Intelligence</h2>
      <p>Signal-first workflow with research, risk and execution in one interface.</p>
      <div class="stats">
        <div><span>Latency</span><strong>12ms</strong></div>
        <div><span>Win Rate</span><strong>68.4%</strong></div>
        <div><span>Uptime</span><strong>99.99%</strong></div>
      </div>
    </section>

    <div class="login-card">
      <div class="card-top">
        <span class="status-dot" />
        <span>SECURE TERMINAL</span>
      </div>
      <h1>Jarvis</h1>
      <p class="subtitle">Sign in to access your trading cockpit</p>

      <el-form class="login-form" @submit.prevent>
        <el-form-item label="账号">
          <el-input v-model="account" placeholder="请输入账号" size="large" clearable />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            type="password"
            show-password
            placeholder="请输入密码"
            size="large"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-button class="submit-btn" type="primary" size="large" @click="submit">
          进入系统
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['login'])
const account = ref('')
const password = ref('')
const THEME_KEY = 'jarvis-theme'
const theme = ref(localStorage.getItem(THEME_KEY) === 'light' ? 'light' : 'dark')

function setTheme(nextTheme) {
  theme.value = nextTheme
  localStorage.setItem(THEME_KEY, nextTheme)
  document.documentElement.setAttribute('data-theme', nextTheme)
  document.body.setAttribute('data-theme', nextTheme)
}

function submit() {
  emit('login', { account: account.value.trim(), password: password.value })
}

document.documentElement.setAttribute('data-theme', theme.value)
document.body.setAttribute('data-theme', theme.value)
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 24px clamp(20px, 7vw, 96px);
  overflow: hidden;
  background: #0b1020;
}

.theme-switch {
  position: absolute;
  left: 24px;
  top: 20px;
  z-index: 4;
  display: inline-flex;
  padding: 4px;
  border-radius: 999px;
  border: 1px solid rgba(135, 154, 186, 0.34);
  background: rgba(16, 25, 40, 0.72);
  backdrop-filter: blur(8px);
}

.theme-btn {
  height: 30px;
  min-width: 62px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: #9baecf;
  font-size: 12px;
  cursor: pointer;
}

.theme-btn.active {
  background: rgba(94, 137, 200, 0.32);
  color: #eef5ff;
}

.bg-layer {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.bg-layer::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 64% 56% at 18% 34%, rgba(84, 132, 255, 0.28), transparent 62%),
    radial-gradient(ellipse 56% 48% at 72% 18%, rgba(100, 232, 255, 0.2), transparent 64%),
    radial-gradient(ellipse 48% 40% at 66% 78%, rgba(136, 104, 255, 0.2), transparent 70%),
    linear-gradient(120deg, #070d1f 0%, #070b18 44%, #050910 100%);
  filter: saturate(1.03) contrast(1.02) brightness(0.95);
}

.mesh {
  position: absolute;
  border-radius: 50%;
  filter: blur(64px);
  opacity: 0.2;
}

.mesh-a {
  width: min(42vw, 520px);
  height: min(42vw, 520px);
  left: -8%;
  top: -10%;
  background: rgba(65, 124, 255, 0.28);
  animation: none;
}

.mesh-b {
  width: min(34vw, 420px);
  height: min(34vw, 420px);
  left: 28%;
  bottom: -12%;
  background: rgba(72, 218, 255, 0.2);
  animation: none;
}

.mesh-c {
  width: min(30vw, 360px);
  height: min(30vw, 360px);
  right: -5%;
  top: 12%;
  background: rgba(140, 96, 255, 0.14);
  animation: none;
}

.grain {
  position: absolute;
  inset: -120px;
  background: radial-gradient(rgba(255, 255, 255, 0.05) 0.7px, transparent 1px);
  background-size: 3px 3px;
  opacity: 0.05;
}

.grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(137, 164, 215, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(137, 164, 215, 0.08) 1px, transparent 1px);
  background-size: 42px 42px;
  mask-image: radial-gradient(ellipse 56% 62% at 28% 50%, #000 12%, transparent 72%);
  opacity: 0.26;
}

.light-beam {
  position: absolute;
  left: -22%;
  top: 0;
  width: 44%;
  height: 100%;
  background: linear-gradient(
    105deg,
    transparent 0%,
    rgba(126, 199, 255, 0.02) 40%,
    rgba(126, 199, 255, 0.15) 50%,
    rgba(126, 199, 255, 0.02) 60%,
    transparent 100%
  );
  animation: none;
  opacity: 0.35;
}

.hero-copy {
  position: absolute;
  left: clamp(22px, 6vw, 88px);
  top: 50%;
  transform: translateY(-50%);
  width: min(46vw, 620px);
  z-index: 2;
  color: #e8f0ff;
}

.pill {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 14px;
  border-radius: 999px;
  font-size: 11px;
  letter-spacing: 0.14em;
  color: #a5b7d8;
  border: 1px solid rgba(133, 154, 190, 0.38);
  background: rgba(25, 34, 54, 0.46);
  margin-bottom: 18px;
}

.hero-copy h2 {
  margin: 0;
  font-size: clamp(32px, 3.8vw, 50px);
  line-height: 1.04;
  letter-spacing: -0.02em;
  color: #f4f8ff;
}

.hero-copy p {
  margin: 14px 0 0;
  max-width: 560px;
  color: #9ba9c3;
  font-size: 15px;
  line-height: 1.65;
}

.stats {
  margin-top: 26px;
  display: grid;
  grid-template-columns: repeat(3, minmax(100px, 1fr));
  gap: 12px;
  max-width: 520px;
}

.stats div {
  border: 1px solid rgba(120, 138, 170, 0.24);
  background: rgba(18, 26, 42, 0.48);
  border-radius: 12px;
  padding: 10px 12px;
}

.stats span {
  display: block;
  font-size: 11px;
  color: #94a5c4;
  margin-bottom: 6px;
}

.stats strong {
  font-size: 17px;
  color: #d5deee;
  font-weight: 650;
}

.scan-line {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background: repeating-linear-gradient(
    to bottom,
    rgba(190, 214, 255, 0.02) 0px,
    rgba(190, 214, 255, 0.02) 2px,
    transparent 2px,
    transparent 6px
  );
  opacity: 0.2;
}

.login-card {
  position: relative;
  z-index: 3;
  width: min(410px, 100%);
  padding: 30px 28px 24px;
  border-radius: 20px;
  border: 1px solid rgba(129, 146, 175, 0.32);
  background:
    linear-gradient(155deg, rgba(8, 20, 40, 0.72), rgba(7, 15, 32, 0.66)),
    rgba(8, 18, 36, 0.66);
  backdrop-filter: blur(18px);
  box-shadow:
    0 28px 56px rgba(0, 0, 0, 0.44),
    0 0 0 rgba(86, 152, 255, 0),
    inset 0 1px 0 rgba(212, 236, 255, 0.08);
  color: #e8f3ff;
  overflow: hidden;
}

.login-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  border: 1px solid rgba(180, 214, 255, 0.1);
  pointer-events: none;
}

.card-top {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 11px;
  letter-spacing: 0.16em;
  color: #aab8d0;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #6fbeff;
  box-shadow: none;
  animation: none;
}

h1 {
  position: relative;
  margin: 0;
  font-size: 32px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #f2f7ff;
  text-shadow: none;
}

.subtitle {
  margin: 8px 0 20px;
  color: #9aa9c4;
  font-size: 13px;
}

.login-form {
  position: relative;
}

:deep(.el-form-item) {
  margin-bottom: 18px;
}

:deep(.el-form-item__label) {
  color: #afc7ec;
  font-weight: 500;
}

:deep(.el-input__wrapper) {
  min-height: 46px;
  border-radius: 12px;
  background: rgba(8, 20, 42, 0.62);
  box-shadow: 0 0 0 1px rgba(120, 168, 235, 0.24) inset !important;
  transition: box-shadow 0.2s ease, background 0.2s ease;
}

:deep(.el-input__wrapper:hover),
:deep(.el-input__wrapper.is-focus) {
  background: rgba(10, 26, 52, 0.78);
  box-shadow: 0 0 0 1px rgba(132, 168, 220, 0.52) inset !important;
}

:deep(.el-input__inner) {
  color: #e7f3ff;
}

.submit-btn {
  width: 100%;
  margin-top: 4px;
  height: 46px;
  border: none;
  border-radius: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  --el-color-primary: #3e6fb4;
  --el-color-primary-light-3: #5f89c8;
  --el-color-primary-dark-2: #355f99;
  box-shadow: none;
}

@keyframes bgPulse {
  from { transform: scale(1.01); }
  to { transform: scale(1.03); }
}

.theme-light {
  background: #eef3f9;
}

.theme-light .theme-switch {
  border-color: rgba(151, 170, 198, 0.55);
  background: rgba(247, 251, 255, 0.8);
}

.theme-light .theme-btn {
  color: #6a7d98;
}

.theme-light .theme-btn.active {
  background: rgba(70, 118, 192, 0.16);
  color: #304d78;
}

.theme-light .bg-layer::before {
  background:
    radial-gradient(ellipse 64% 56% at 18% 34%, rgba(83, 143, 255, 0.2), transparent 62%),
    radial-gradient(ellipse 56% 48% at 72% 18%, rgba(107, 211, 255, 0.15), transparent 64%),
    radial-gradient(ellipse 48% 40% at 66% 78%, rgba(151, 124, 255, 0.14), transparent 70%),
    linear-gradient(120deg, #edf3fb 0%, #e6eef8 44%, #dde7f5 100%);
}

.theme-light .grain,
.theme-light .scan-line {
  opacity: 0.08;
}

.theme-light .grid {
  opacity: 0.2;
}

.theme-light .hero-copy {
  color: #1f3654;
}

.theme-light .pill {
  color: #47658d;
  border-color: rgba(117, 149, 196, 0.4);
  background: rgba(232, 241, 253, 0.9);
}

.theme-light .hero-copy h2 {
  color: #0f2742;
}

.theme-light .hero-copy p {
  color: #5e7595;
}

.theme-light .stats div {
  border-color: rgba(133, 160, 200, 0.44);
  background: rgba(238, 245, 255, 0.84);
}

.theme-light .stats span {
  color: #5a7396;
}

.theme-light .stats strong {
  color: #26466d;
}

.theme-light .login-card {
  border-color: rgba(146, 169, 203, 0.55);
  background:
    linear-gradient(155deg, rgba(255, 255, 255, 0.85), rgba(246, 250, 255, 0.8)),
    rgba(255, 255, 255, 0.82);
  box-shadow:
    0 20px 44px rgba(88, 118, 159, 0.16),
    inset 0 1px 0 rgba(255, 255, 255, 0.72);
  color: #294567;
}

.theme-light .login-card::before {
  border-color: rgba(177, 198, 226, 0.5);
}

.theme-light .card-top {
  color: #5d789d;
}

.theme-light .status-dot {
  background: #5f89c8;
}

.theme-light h1 {
  color: #173459;
}

.theme-light .subtitle {
  color: #657f9f;
}

.theme-light :deep(.el-form-item__label) {
  color: #58739a;
}

.theme-light :deep(.el-input__wrapper) {
  background: rgba(248, 251, 255, 0.95);
  box-shadow: 0 0 0 1px rgba(162, 185, 217, 0.6) inset !important;
}

.theme-light :deep(.el-input__wrapper:hover),
.theme-light :deep(.el-input__wrapper.is-focus) {
  background: #ffffff;
  box-shadow: 0 0 0 1px rgba(92, 132, 191, 0.62) inset !important;
}

.theme-light :deep(.el-input__inner) {
  color: #234264;
}

.theme-light .submit-btn {
  --el-color-primary: #3f6fb4;
  --el-color-primary-light-3: #5f89c8;
  --el-color-primary-dark-2: #32598f;
}

@media (max-width: 900px) {
  .login-page {
    justify-content: center;
    padding: 20px;
  }

  .theme-switch {
    left: 50%;
    transform: translateX(-50%);
    top: 14px;
  }

  .hero-copy {
    display: none;
  }

  .login-card {
    width: min(420px, 100%);
  }
}
</style>
