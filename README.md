# TRACE: Traces of the Unconscious

Recording Invisible Time Through Heartbeats

TRACE is a real-time generative art system that transforms heart rate data from wearable devices into evolving visual artworks.

Using Bluetooth Low Energy (BLE), the system reads physiological signals from a Garmin device and converts them into an interactive digital canvas inspired by painterly styles such as Gogh, Monet, and Picasso.

Rather than treating biometric data as a health metric, TRACE reinterprets it as an artistic medium for reflection, memory, and emotional awareness.

------------------------------------------------------------

PROJECT OBJECTIVE

TRACE visualises the unconscious passage of time through physiological signals that people do not intentionally control.

By collecting heart rate data in real time and translating it into generative visual patterns, the system produces a personal visual archive of a user's internal rhythm throughout the day.

The final output is not a medical report, but a layered artistic trace of lived experience.

------------------------------------------------------------

MOTIVATION

People often say that time passes quickly.

However, time may feel fast because many moments pass without conscious awareness. Even when we do not notice them, our bodies still respond to stimuli.

TRACE was developed from the idea that:

Even when a moment is forgotten consciously, it may still remain as a trace in the body.

Heart rate was selected as the primary signal because it is:

- continuously present in everyday life
- difficult to consciously manipulate
- sensitive to emotional and cognitive states

Examples include:

- stress
- calmness
- focus
- stimulation

Through this system, subtle physiological changes become visual evidence of otherwise invisible time.

------------------------------------------------------------

CORE FEATURES

Real-time BLE Heart Rate Acquisition

TRACE connects to a Garmin device using Bleak and receives live heart rate data over Bluetooth Low Energy.

Baseline Learning

The system begins in an observation mode, where it gradually learns the user's baseline heart rate before generating strong visual responses.

Expressiveness Mapping

Heart rate variations are converted into an expressiveness parameter that controls how actively the artwork evolves.

Multi-Style Generative Art Engine

Users can switch between artistic modes:

DEFAULT  
GOGH  
MONET  
PICASSO  

Each mode responds differently to physiological input.

Temporal Archiving

The canvas is sampled every 2 seconds, and a summary image is saved every 10 minutes.

Final Trace Generation

At the end of the session, all summary layers are combined into a final trace artwork using temporal decay and layered accumulation.

Session Video Output

Saved summary images are automatically combined into a time-lapse session video.

------------------------------------------------------------

SYSTEM ARCHITECTURE

Physiological Input  
  -> Garmin Wearable Device  
  -> BLE Heart Rate Notification  

Signal Processing  
  -> Heart Rate Smoothing  
  -> Baseline Adaptation  
  -> Stress Estimation  
  -> Expressiveness Calculation  

Generative Art Engine  
  -> Pygame Real-time Canvas  
  -> Style-dependent Visual Units  
  -> Gogh / Monet / Picasso Modes  

Temporal Recording  
  -> Frame Sampling (2 sec)  
  -> Summary Images (10 min)  

Final Output  
  -> Final Trace Image  
  -> Session Movie  
  -> Session Summary Text  

------------------------------------------------------------

TECHNICAL STACK

Python  
Pygame (real-time generative rendering)  
Bleak (Bluetooth Low Energy communication)  
NumPy (signal and image processing)  
OpenCV (video generation)  
Asyncio + Threading (asynchronous BLE communication)

------------------------------------------------------------

HOW THE SYSTEM WORKS

BLE Heart Rate Acquisition

The system connects to a Garmin device and subscribes to the BLE Heart Rate Measurement characteristic.

HEART_RATE_UUID = 00002a37-0000-1000-8000-00805f9b34fb

Incoming packets update:

- current heart rate
- smoothed heart rate
- baseline heart rate
- heart rate delta
- stress estimation

------------------------------------------------------------

BASELINE LEARNING

TRACE starts in an observation phase where it gradually learns a baseline heart rate.

baseline_hr = baseline_hr * (1 - BASELINE_ALPHA) + smoothed_hr * BASELINE_ALPHA

The system waits until the baseline stabilises before activating full generative behaviour.

------------------------------------------------------------

EXPRESSIVENESS CALCULATION

Visual activity is controlled by an internal parameter called expressiveness.

e = np.tanh(abs(hr_state) / 8.0 + hr_delta / 6.0)

Expressiveness determines:

- number of visual elements
- movement speed
- drawing intensity

During observation mode, expressiveness is intentionally reduced to keep the canvas calm.

------------------------------------------------------------

GENERATOR MODES

GOGH MODE  
- swirling strokes  
- energetic motion  
- expressive lines  

MONET MODE  
- soft colour diffusion  
- circular forms  
- atmospheric impression  

PICASSO MODE  
- geometric polygons  
- fragmented shapes  
- structured abstraction  

DEFAULT MODE  
- simple circular traces  

------------------------------------------------------------

TEMPORAL SAMPLING

The live canvas is sampled every 2 seconds.

SAMPLE_INTERVAL_SEC = 2

Frames are averaged over time.

Every 10 minutes the accumulated frame is saved as a summary image.

SUMMARY_WINDOW_SEC = 10 * 60

------------------------------------------------------------

FINAL TRACE GENERATION

At the end of the session, summary images are combined using:

- temporal blending
- dark decay
- tone mapping

Example logic:

final_accum *= dark_decay  
final_accum = final_accum * (1 - alpha) + arr * alpha

Older layers gradually fade while meaningful variations remain visible.

------------------------------------------------------------

SESSION VIDEO CREATION

All summary images are compiled into a session video using OpenCV.

video = cv2.VideoWriter(output_path, fourcc, 2, (width, height))

The video shows the evolution of the artwork over time.

------------------------------------------------------------

FILE OUTPUTS

Each run automatically creates a new session directory.

Example:

gallery/

20260314/  
session_20260314_153012/  

summary_001.png  
summary_002.png  
summary_003.png  

final_trace.png  

session_movie.mp4  

session_summary.txt  

------------------------------------------------------------

CONTROLS

Keyboard shortcuts during runtime

G -> Gogh Mode  
M -> Monet Mode  
P -> Picasso Mode  
D -> Default Mode  
ESC -> Exit session  

------------------------------------------------------------

INSTALLATION

pip install pygame bleak numpy opencv-python

------------------------------------------------------------

RUN

Set your wearable device address inside the code.

TARGET_ADDRESS = YOUR_DEVICE_ADDRESS

Run the program:

python trace.py

------------------------------------------------------------

PROJECT STRUCTURE

TRACE

trace.py  
gallery  

generated sessions  
summary images  
final trace  
session video  

README.md

------------------------------------------------------------

ARTISTIC PERSPECTIVE

TRACE is not a health monitoring tool.

Instead, it explores the relationship between physiological signals, memory, unconscious perception, and the passage of time.

By converting invisible bodily rhythms into visual forms, the project suggests that even when moments feel lost, they may still leave traces within us.

------------------------------------------------------------

FUTURE WORK

EEG-based unconscious visualisation  
VR generative environments  
interactive gallery installation  
multi-user trace visualisation  
long-term personal trace archive

------------------------------------------------------------

AUTHOR

TRACE is an experimental project exploring the intersection of generative art, physiological computing, interactive media, and human perception of time.
