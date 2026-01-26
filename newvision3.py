import threading
import asyncio
import pygame
import random
import cv2
import numpy as np
import sys
import os
import time
from datetime import datetime
from bleak import BleakClient

# =========================================================
# USER SETTINGS
# =========================================================
TARGET_ADDRESS = "14:13:0B:2B:CE:26"
WIDTH, HEIGHT = 1000, 800
HEART_RATE_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

SUMMARY_WINDOW_SEC = 10 * 60  # 10분마다 요약본 저장
SAMPLE_INTERVAL_SEC = 2       # 2초마다 화면 샘플링

# =========================================================
# GLOBAL STATE
# =========================================================
current_hr = 70
smoothed_hr = 70.0
prev_smoothed_hr = 70.0
baseline_hr = 70.0
hr_delta = 0.0
current_stress = 30.0

is_running = True
is_connected = False
current_mode = "DEFAULT"

hr_history = []
summary_raw_list = []

BASELINE_ALPHA = 0.002
OBSERVE_MIN_SEC = 5 * 60
BASELINE_STABLE_WINDOW = 60
BASELINE_STABLE_EPS = 1.5

is_observing = True
observe_start_time = None
baseline_trace = []

# =========================================================
# SYSTEM UTILS
# =========================================================
def make_unique_session_dir(root="gallery"):
    date_dir = datetime.now().strftime("%Y%m%d")
    time_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(root, date_dir)
    os.makedirs(base, exist_ok=True)
    session_dir = os.path.join(base, f"session_{time_tag}")
    if not os.path.exists(session_dir):
        os.makedirs(session_dir)
        return session_dir
    i = 2
    while True:
        candidate = os.path.join(base, f"session_{time_tag}_v{i}")
        if not os.path.exists(candidate):
            os.makedirs(candidate)
            return candidate
        i += 1

def tone_map_mean_image(img_f32):
    x = np.clip(img_f32 / 255.0, 0.0, 1.0).astype(np.float32)
    sat = 1.15 if current_mode == 'PICASSO' else 1.8
    lift, gamma = 0.01, 0.58 
    x = np.clip(x + lift, 0.0, 1.0)
    x = np.power(x, gamma)
    mean = x.mean(axis=2, keepdims=True)
    x = mean + (x - mean) * sat
    out = np.empty_like(x)
    for c in range(3):
        lo = np.percentile(x[..., c], 1.0)
        hi = np.percentile(x[..., c], 99.3)
        out[..., c] = (x[..., c] - lo) / (hi - lo + 1e-6)
    out = np.clip(out, 0.0, 1.0)
    out = out / (out + 0.35)
    return (out * 255.0).astype(np.uint8)

def save_array_as_png(arr_u8, path):
    surf = pygame.surfarray.make_surface(np.transpose(arr_u8, (1, 0, 2)))
    pygame.image.save(surf, path)

def create_final_trace_from_raw(
    raw_list,
    out_path,
    alpha=0.18,
    dark_decay=0.992
):
    """
    final_trace 생성 (관조 보호 버전)

    - raw_list      : 보정 전 RAW summary(accum) 리스트
    - alpha         : 새 구간 반영 비율 (0.12~0.22 추천)
    - dark_decay    : 관조 감쇠 계수 (0.99~0.995 추천)
                      ↓ 작을수록 오래 관찰해도 하얘지지 않음
    """

    if not raw_list:
        return

    alpha = float(np.clip(alpha, 0.01, 0.6))
    dark_decay = float(np.clip(dark_decay, 0.90, 0.9999))

    final_accum = None

    for arr in raw_list:
        arr = arr.astype(np.float32)

        if final_accum is None:
            # 첫 구간은 기준 레이어
            final_accum = arr.copy()
        else:
            # ✅ 핵심 1: 관조 감쇠 (시간 누적 밝기 억제)
            final_accum *= dark_decay

            # ✅ 핵심 2: 색 유지 누적
            final_accum = final_accum * (1.0 - alpha) + arr * alpha

    # ✅ 톤매핑은 여기서 단 1번만
    final_u8 = tone_map_mean_image(final_accum)
    save_array_as_png(final_u8, out_path)


def save_session_text(base_dir, summary_paths, final_trace_path, started_at, ended_at):
    start_str = datetime.fromtimestamp(started_at).strftime('%Y-%m-%d %H:%M:%S')
    end_str = datetime.fromtimestamp(ended_at).strftime('%Y-%m-%d %H:%M:%S')
    duration = int(ended_at - started_at)
    lines = [
        "TRACE / SESSION SUMMARY",
        "========================",
        f"Start Time:    {start_str}",
        f"End Time:      {end_str}",
        f"Duration:      {duration // 60} min {duration % 60} sec",
        f"Final mode:    {current_mode}",
        f"Last HR:       {current_hr}",
        f"Baseline HR:   {baseline_hr:.2f}",
        f"Stress Score:  {int(current_stress)}",
        "", "FILES:"
    ]
    for p in summary_paths: lines.append(f"- {os.path.basename(p)}")
    lines.append(f"- {os.path.basename(final_trace_path)}")
    with open(os.path.join(base_dir, "session_summary.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# =========================================================
# BLE WORKER
# =========================================================
async def garmin_worker():
    global current_hr, smoothed_hr, prev_smoothed_hr, baseline_hr, hr_delta, current_stress
    global is_connected, is_observing, observe_start_time, baseline_trace
    while is_running:
        try:
            async with BleakClient(TARGET_ADDRESS, timeout=10.0) as client:
                is_connected = client.is_connected
                def callback(_, data):
                    global current_hr, smoothed_hr, prev_smoothed_hr, baseline_hr, hr_delta, current_stress, is_observing, observe_start_time, baseline_trace
                    current_hr = int(data[1])
                    prev_smoothed_hr = smoothed_hr
                    smoothed_hr = smoothed_hr * 0.9 + current_hr * 0.1
                    hr_delta = abs(smoothed_hr - prev_smoothed_hr)
                    if observe_start_time is None: observe_start_time = time.time()
                    baseline_hr = baseline_hr * (1 - BASELINE_ALPHA) + smoothed_hr * BASELINE_ALPHA
                    now = time.time()
                    baseline_trace.append((now, baseline_hr))
                    baseline_trace = [(t, b) for t, b in baseline_trace if now - t < BASELINE_STABLE_WINDOW]
                    if is_observing and (now - observe_start_time) > OBSERVE_MIN_SEC:
                        vals = [b for _, b in baseline_trace]
                        if len(vals) >= 5 and (max(vals) - min(vals)) < BASELINE_STABLE_EPS:
                            is_observing = False
                    hr_state = smoothed_hr - baseline_hr
                    current_stress = float(np.clip(abs(hr_state) * 1.2 + hr_delta * 2.0, 0, 100))
                
                await client.start_notify(HEART_RATE_UUID, callback)
                while is_running and client.is_connected: await asyncio.sleep(1)
        except:
            is_connected = False
            await asyncio.sleep(3)

# =========================================================
# ART UNIT
# =========================================================
def compute_expressiveness():
    hr_state = smoothed_hr - baseline_hr
    e = np.tanh(abs(hr_state) / 8.0 + hr_delta / 6.0)
    return float(np.clip(e * (0.35 if is_observing else 1.0), 0.0, 1.0))    #관찰 모드일때는 계산된 값의 35%로만 반영, 기준이 잡히기 전 화면이 너무 요동치는 것을 방지 

class ArtUnit:
    def __init__(self, x, y, mode, expr):
        self.pos = np.array([float(x), float(y)], dtype=np.float32)
        self.mode, self.expr, self.life = mode, expr, 255.0
        self.angle = random.uniform(0, np.pi * 2)
        self.setup_style()

    def setup_style(self):
        if self.mode == "GOGH":
            self.color = random.choice([[255,210,0],[40,70,150],[240,240,230]])
            self.stroke_len, self.life_decay = random.randint(16, 28), 2.5
            v = np.random.uniform(-1, 1, 2)
            self.vel = v / (np.linalg.norm(v)+1e-6) * (2.0 + self.expr)
        elif self.mode == "MONET":
            self.color = random.choice([[170,220,255],[200,180,255],[140,240,180]])
            self.size, self.life_decay = random.randint(20, 55), 1.3
            self.vel = np.random.uniform(-0.15, 0.15, 2)
        elif self.mode == "PICASSO":
            self.color = random.choice([[60,60,70],[200,60,50],[40,120,160]])
            self.size, self.sides, self.life_decay = random.randint(30, 55), random.choice([3,4]), 1.1
            v = np.random.uniform(-1, 1, 2)
            self.vel = v / (np.linalg.norm(v)+1e-6) * (0.9 + self.expr)
        else:
            self.color, self.size, self.life_decay = [120,200,255], random.randint(3,6), 1.4
            self.vel = np.random.uniform(-1,1,2)

    def update(self):
        if self.mode == "GOGH":
            d = np.array([WIDTH/2, HEIGHT/2]) - self.pos
            self.vel += np.array([-d[1], d[0]]) * 0.002
        elif self.mode == "PICASSO": self.angle += 0.04 + self.expr*0.05
        self.pos += self.vel
        self.life -= self.life_decay

    def draw(self, surf):
        if self.life <= 0: return
        x, y, a = int(self.pos[0]), int(self.pos[1]), int(self.life)
        if self.mode == "GOGH":
            d = self.vel / (np.linalg.norm(self.vel)+1e-6)
            l = int(self.stroke_len*(0.8+self.expr))
            pygame.draw.line(surf, (*self.color, a), (x,y), (x+d[0]*l, y+d[1]*l), 2)
        elif self.mode == "MONET":
            pygame.draw.circle(surf, (*self.color, int(a * 0.4)), (x,y), self.size)
        elif self.mode == "PICASSO":
            pts = [(x+np.cos(self.angle+i*2*np.pi/self.sides)*self.size, y+np.sin(self.angle+i*2*np.pi/self.sides)*self.size) for i in range(self.sides)]
            pygame.draw.polygon(surf, (*self.color, a), pts, 2)
        else:
            pygame.draw.circle(surf, (*self.color, a), (x,y), self.size)

def create_session_video(base_dir, video_name="session_movie.mp4"):
    # 1. summary_로 시작하는 png 파일들만 정렬해서 가져오기
    images = [img for img in os.listdir(base_dir) if img.startswith("summary_") and img.endswith(".png")]
    images.sort() # 번호순 정렬

    if not images:
        print("영상으로 만들 이미지가 없습니다.")
        return

    # 2. 첫 번째 이미지로 영상 크기 설정
    first_img = cv2.imread(os.path.join(base_dir, images[0]))         
    height, width, layers = first_img.shape
    
    # 3. 비디오 코덱 및 객체 생성 (MP4V 코덱 사용)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
    video = cv2.VideoWriter(os.path.join(base_dir, video_name), fourcc, 2, (width, height)) # 2fps: 초당 2장씩

    for image in images:
        img_path = os.path.join(base_dir, image)
        frame = cv2.imread(img_path)
        video.write(frame)

    video.release()
    print(f"영상 제작 완료: {video_name}")


# =========================================================
# MAIN
# =========================================================
def run_system():
    global is_running, current_mode, summary_raw_list
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("TRACE(d:Default g:Gogh m:Monet p:Picasso)")
    canvas = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    clock = pygame.time.Clock()

    base_dir = make_unique_session_dir()
    session_started_at = time.time()
    
    units, summary_paths = [], []
    accum, samples = None, 0
    window_start, last_sample = time.time(), 0.0

    # 폰트 로드 (없을 경우 기본 폰트)
    try: font = pygame.font.SysFont("malgungothic", 16)
    except: font = pygame.font.SysFont("arial", 16)

    while is_running:
        expr = compute_expressiveness()
        
        # 1. 배경 채우기 (모네 모드 하얗게 방지)
        if current_mode == "MONET":
            canvas.fill((15, 20, 30, 50)) 
        elif current_mode == "PICASSO":
            canvas.fill((18, 18, 18, 16))
        else:
            canvas.fill((15, 20, 15, 16))

        # 2. 유닛 생성
        if is_connected and random.random() < (0.02 + expr*0.04):  #새로운 원이 생성될 확률
            units.append(ArtUnit(random.randint(0,WIDTH), random.randint(0,HEIGHT), current_mode, expr))

        # 3. 업데이트/그리기
        for u in units[:]:
            u.update()
            u.draw(canvas)
            if u.life <= 0: units.remove(u)

        screen.blit(canvas, (0,0))
        
        # 4. UI
        status_color = (100, 255, 100) if is_connected else (255, 100, 100)
        ui_lines = [
            f"MODE: {current_mode}", f"HR: {current_hr} (smth: {smoothed_hr:.1f})",
            f"BASE: {baseline_hr:.1f} | Δ: {hr_delta:.2f}",
            f"STRESS: {int(current_stress)} | EXPR: {expr:.2f}",
            f"STATE: {'OBSERVING' if is_observing else 'ACTIVE'}",
            f"BLE: {'CONNECTED' if is_connected else 'RECONNECTING...'}"
        ]
        y = 20
        for line in ui_lines:
            screen.blit(font.render(line, True, (220, 220, 220)), (20, y))
            y += 20
        screen.blit(font.render("●", True, status_color), (5, 20))

        pygame.display.flip()
        clock.tick(60)

        # 5. 샘플링/저장
        now = time.time()
        if now - last_sample >= SAMPLE_INTERVAL_SEC:
            last_sample = now
            frame = np.transpose(pygame.surfarray.array3d(canvas), (1,0,2)).astype(np.float32)
            accum = frame if accum is None else accum + (frame - accum) / (samples + 1)
            samples += 1

        if now - window_start >= SUMMARY_WINDOW_SEC and accum is not None:
            summary_raw_list.append(accum.copy())
            out = tone_map_mean_image(accum)
            p = os.path.join(base_dir, f"summary_{len(summary_paths)+1:03d}.png")
            save_array_as_png(out, p)
            summary_paths.append(p)
            accum, samples, window_start = None, 0, now

        for e in pygame.event.get():
            if e.type == pygame.QUIT: is_running = False
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE: is_running = False
                elif e.key == pygame.K_g: current_mode = "GOGH"
                elif e.key == pygame.K_m: current_mode = "MONET"
                elif e.key == pygame.K_p: current_mode = "PICASSO"
                elif e.key == pygame.K_d: current_mode = "DEFAULT"

    # --- 종료 처리 ---
    session_ended_at = time.time()
    if accum is not None:
        summary_raw_list.append(accum.copy())
        out = tone_map_mean_image(accum)
        final_summary = os.path.join(base_dir, "JB.png")
        save_array_as_png(out, final_summary)
        summary_paths.append(final_summary)

    final_trace = os.path.join(base_dir, "final_trace.png")

    final_trace = os.path.join(base_dir, "final_trace.png")

    create_final_trace_from_raw(
        summary_raw_list,
        final_trace,
        alpha=0.18,
        dark_decay=0.992
    )

    save_session_text(base_dir, summary_paths, final_trace, session_started_at, session_ended_at)
    
    # [추가] 10분마다 저장된 요약본들을 영상으로 변환
    create_session_video(base_dir)

    
    pygame.quit()
    print(f"세션 종료. 저장 경로: {base_dir}")
    sys.exit()

if __name__ == "__main__":
    if sys.platform == "win32": asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    threading.Thread(target=lambda: asyncio.run(garmin_worker()), daemon=True).start()
    run_system()