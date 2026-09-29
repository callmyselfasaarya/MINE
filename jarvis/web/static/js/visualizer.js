/**
 * M.I.N.E. Audio Waveform & Arc Reactor Visualizer
 */
class AudioWaveformVisualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.state = 'idle'; // idle | listening | processing | speaking
    this.phase = 0;
    this.audioContext = null;
    this.analyser = null;
    this.dataArray = null;

    this.resize();
    window.addEventListener('resize', () => this.resize());
    this.animate();
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.canvas.getBoundingClientRect();
    this.canvas.width = rect.width * window.devicePixelRatio;
    this.canvas.height = rect.height * window.devicePixelRatio;
    this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    this.width = rect.width;
    this.height = rect.height;
  }

  setState(newState) {
    this.state = newState;
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    if (!this.ctx || !this.width) return;

    this.ctx.clearRect(0, 0, this.width, this.height);
    this.phase += 0.05;

    const centerY = this.height / 2;
    const points = 60;
    const step = this.width / points;

    this.ctx.beginPath();
    this.ctx.lineWidth = 2;

    // Set styling based on state
    if (this.state === 'listening') {
      this.ctx.strokeStyle = '#00ffaa';
      this.ctx.shadowColor = '#00ffaa';
      this.ctx.shadowBlur = 12;
    } else if (this.state === 'processing') {
      this.ctx.strokeStyle = '#ffb700';
      this.ctx.shadowColor = '#ffb700';
      this.ctx.shadowBlur = 10;
    } else if (this.state === 'speaking') {
      this.ctx.strokeStyle = '#00f3ff';
      this.ctx.shadowColor = '#00f3ff';
      this.ctx.shadowBlur = 16;
    } else {
      this.ctx.strokeStyle = 'rgba(0, 243, 255, 0.4)';
      this.ctx.shadowColor = 'rgba(0, 243, 255, 0.2)';
      this.ctx.shadowBlur = 4;
    }

    let amp = 4;
    let freq = 0.08;
    if (this.state === 'listening') {
      amp = 14;
      freq = 0.14;
    } else if (this.state === 'processing') {
      amp = 8;
      freq = 0.22;
    } else if (this.state === 'speaking') {
      amp = 18;
      freq = 0.12;
    }

    for (let i = 0; i <= points; i++) {
      const x = i * step;
      // Damped envelope at ends
      const envelope = Math.sin((i / points) * Math.PI);
      const y = centerY + Math.sin(i * freq + this.phase) * amp * envelope;

      if (i === 0) {
        this.ctx.moveTo(x, y);
      } else {
        this.ctx.lineTo(x, y);
      }
    }
    this.ctx.stroke();

    // Mirror wave for sci-fi symmetry
    if (this.state === 'speaking' || this.state === 'listening') {
      this.ctx.beginPath();
      this.ctx.lineWidth = 1;
      this.ctx.strokeStyle = 'rgba(0, 136, 255, 0.6)';
      for (let i = 0; i <= points; i++) {
        const x = i * step;
        const envelope = Math.sin((i / points) * Math.PI);
        const y = centerY - Math.sin(i * freq + this.phase * 1.2) * (amp * 0.7) * envelope;
        if (i === 0) this.ctx.moveTo(x, y);
        else this.ctx.lineTo(x, y);
      }
      this.ctx.stroke();
    }
  }
}

window.AudioWaveformVisualizer = AudioWaveformVisualizer;