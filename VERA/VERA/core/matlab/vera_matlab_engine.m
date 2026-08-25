%% ============================================================================
%% VERA — Verification Engine for Runtime & Autonomous Checking
%% FILE: core/matlab/vera_matlab_engine.m
%% DESC: MATLAB/Octave post-simulation checker engine.
%%       Supports ADC (FFT, DNL/INL), PLL (jitter, lock), filter (freq response),
%%       and generic parametric checks. Produces VERA JSON reports.
%% VERSION: 1.0
%% USAGE:
%%   results = vera_run('sar_adc_spec.json', 'sim_data.mat');
%%   vera_write_report(results, 'vera_matlab_report.json');
%% ============================================================================

function vera_matlab_engine()
  fprintf('\n  VERA MATLAB Engine v1.0\n');
  fprintf('  Verification Engine for Runtime & Autonomous Checking\n\n');
end


%% ============================================================================
%% VERA Result Structure Builder
%% ============================================================================
function r = vera_result(ip, checker, checker_type, status, expected, actual, margin, ctx, signal, rec)
  r.vera_version   = '1.0';
  r.timestamp      = datestr(now, 'yyyy-mm-ddTHH:MM:SS');
  r.ip_name        = ip;
  r.checker_name   = checker;
  r.checker_type   = checker_type;
  r.layer          = 'parametric';
  r.status         = status;      % 'PASS' | 'FAIL' | 'WARNING'
  r.severity       = ternary(strcmp(status,'PASS'), 'INFO', 'ERROR');
  r.expected       = expected;
  r.actual         = actual;
  r.margin         = margin;
  r.context        = ctx;
  r.debug_signal   = signal;
  r.recommendation = rec;
  % Echo to console
  icon = ternary(strcmp(status,'PASS'), char(10003), char(10007));
  fprintf('  [%s] %s | %s | EXP: %s | ACT: %s\n', ...
          icon, ip, checker, expected, actual);
end


%% ============================================================================
%% VERA Parametric Check
%% ============================================================================
function r = vera_check_param(ip, checker, val, vmin, vmax, unit, signal, ctx)
  in_spec = (val >= vmin) && (val <= vmax);
  status  = ternary(in_spec, 'PASS', 'FAIL');
  margin  = sprintf('lo=%+.4g hi=%+.4g %s', val-vmin, vmax-val, unit);
  r = vera_result(ip, checker, 'matlab_postsim', status, ...
    sprintf('%g to %g %s', vmin, vmax, unit), ...
    sprintf('%g %s', val, unit), margin, ctx, signal, ...
    ternary(in_spec, '', sprintf('%.4g %s out of [%.4g, %.4g] %s', val, unit, vmin, vmax, unit)));
end

function r = vera_check_max(ip, checker, val, vmax, unit, signal, ctx)
  in_spec = val <= vmax;
  r = vera_result(ip, checker, 'matlab_postsim', ternary(in_spec,'PASS','FAIL'), ...
    sprintf('<= %g %s', vmax, unit), sprintf('%g %s', val, unit), ...
    sprintf('%+.4g %s', vmax-val, unit), ctx, signal, ...
    ternary(in_spec, '', sprintf('Exceeds max by %.4g %s', val-vmax, unit)));
end

function r = vera_check_min(ip, checker, val, vmin, unit, signal, ctx)
  in_spec = val >= vmin;
  r = vera_result(ip, checker, 'matlab_postsim', ternary(in_spec,'PASS','FAIL'), ...
    sprintf('>= %g %s', vmin, unit), sprintf('%g %s', val, unit), ...
    sprintf('%+.4g %s', val-vmin, unit), ctx, signal, ...
    ternary(in_spec, '', sprintf('Below min by %.4g %s', vmin-val, unit)));
end


%% ============================================================================
%% VERA ADC Dynamic Checker (FFT-based: ENOB, SNR, SFDR, THD)
%% ============================================================================
function results = vera_check_adc_dynamic(ip_name, codes, fs_hz, fin_hz, spec)
  %% spec: struct with fields enob_min, snr_min_db, sfdr_min_db, thd_max_db
  results = {};
  N       = length(codes);
  codes_f = double(codes) - mean(double(codes));

  % Hann-windowed FFT
  win     = hann(N);
  X       = fft(codes_f .* win);
  X_mag   = abs(X(1:N/2+1)) * 2 / sum(win);
  freqs   = (0:N/2) * fs_hz / N;

  % Fundamental bin
  [~, fund_bin] = min(abs(freqs - fin_hz));
  fund_bins = max(1,fund_bin-2):min(length(X_mag),fund_bin+2);
  sig_power = sum(X_mag(fund_bins).^2);

  % Harmonic bins (2nd–6th)
  harm_bins = [];
  thd_power = 0;
  for h = 2:6
    hbin = mod(h * fund_bin, N/2);
    if hbin < 1, hbin = 1; end
    hb = max(1,hbin-2):min(length(X_mag),hbin+2);
    harm_bins = [harm_bins, hb];
    thd_power = thd_power + sum(X_mag(hb).^2);
  end

  % Noise (exclude DC, fundamental, harmonics)
  all_bins    = 1:length(X_mag);
  noise_bins  = setdiff(all_bins, [1, fund_bins, harm_bins]);
  noise_power = sum(X_mag(noise_bins).^2);

  % Metrics
  snr_db   = 10*log10(sig_power / max(noise_power, 1e-20));
  sinad_db = 10*log10(sig_power / max(noise_power + thd_power, 1e-20));
  enob     = (sinad_db - 1.76) / 6.02;
  thd_db   = 10*log10(max(thd_power, 1e-20) / max(sig_power, 1e-20));

  % SFDR
  spur_bins  = setdiff(all_bins, [1, fund_bins]);
  sfdr_db    = 10*log10(sig_power / max(max(X_mag(spur_bins).^2), 1e-20));

  fprintf('\n  ADC Dynamic Results:\n');
  fprintf('    ENOB    = %.2f bits\n', enob);
  fprintf('    SNR     = %.1f dB\n',  snr_db);
  fprintf('    SFDR    = %.1f dBc\n', sfdr_db);
  fprintf('    THD     = %.1f dBc\n', thd_db);
  fprintf('    SINAD   = %.1f dB\n',  sinad_db);

  ctx = sprintf('fin=%.1fkHz fs=%.1fMHz N=%d', fin_hz/1e3, fs_hz/1e6, N);
  if isfield(spec, 'enob_min')
    results{end+1} = vera_check_min(ip_name, 'vera_adc_enob', enob, spec.enob_min, 'bits', 'adc_out', ctx);
  end
  if isfield(spec, 'snr_min_db')
    results{end+1} = vera_check_min(ip_name, 'vera_adc_snr', snr_db, spec.snr_min_db, 'dB', 'adc_out', ctx);
  end
  if isfield(spec, 'sfdr_min_db')
    results{end+1} = vera_check_min(ip_name, 'vera_adc_sfdr', sfdr_db, spec.sfdr_min_db, 'dBc', 'adc_out', ctx);
  end
  if isfield(spec, 'thd_max_db')
    results{end+1} = vera_check_max(ip_name, 'vera_adc_thd', thd_db, spec.thd_max_db, 'dBc', 'adc_out', ctx);
  end
end


%% ============================================================================
%% VERA ADC Static Checker (DNL, INL, Missing Codes)
%% ============================================================================
function results = vera_check_adc_static(ip_name, codes, n_bits, spec)
  results   = {};
  num_codes = 2^n_bits;
  hist_c    = histc(double(codes), 0:num_codes-1);
  ideal_cnt = length(codes) / num_codes;
  dnl       = hist_c / ideal_cnt - 1;
  inl       = cumsum(dnl);

  dnl_inner = dnl(2:end-1);
  inl_inner = inl(2:end-1);

  dnl_max   = max(abs(dnl_inner));
  inl_max   = max(abs(inl_inner));
  [~,widx]  = max(abs(dnl_inner)); worst_dnl_code = widx;
  [~,widx]  = max(abs(inl_inner)); worst_inl_code = widx;
  miss_codes = sum(hist_c(2:end-1) == 0);

  fprintf('\n  ADC Static Results:\n');
  fprintf('    DNL max = %.3f LSB (code %d)\n', dnl_max, worst_dnl_code);
  fprintf('    INL max = %.3f LSB (code %d)\n', inl_max, worst_inl_code);
  fprintf('    Missing = %d codes\n', miss_codes);

  if isfield(spec, 'dnl_max_lsb')
    results{end+1} = vera_check_max(ip_name, 'vera_adc_dnl', dnl_max, spec.dnl_max_lsb, 'LSB', ...
      'adc_out', sprintf('worst at code=%d', worst_dnl_code));
  end
  if isfield(spec, 'inl_max_lsb')
    results{end+1} = vera_check_max(ip_name, 'vera_adc_inl', inl_max, spec.inl_max_lsb, 'LSB', ...
      'adc_out', sprintf('worst at code=%d', worst_inl_code));
  end
  if isfield(spec, 'missing_codes_max')
    results{end+1} = vera_check_max(ip_name, 'vera_adc_missing_codes', miss_codes, ...
      spec.missing_codes_max, 'codes', 'adc_out', 'missing code check');
  end

  % Plot DNL/INL
  figure('Name', sprintf('VERA — %s DNL/INL', ip_name), 'Color', [0.07 0.08 0.09]);
  subplot(2,1,1);
  bar(dnl, 'FaceColor', [0.35 0.66 0.94], 'EdgeColor', 'none');
  title('DNL', 'Color', 'w'); xlabel('Code', 'Color', 'w'); ylabel('LSB', 'Color', 'w');
  yline(spec.dnl_max_lsb, 'r--', 'LineWidth', 1.5);
  yline(-spec.dnl_max_lsb, 'r--', 'LineWidth', 1.5);
  set(gca, 'Color', [0.1 0.1 0.13], 'XColor', 'w', 'YColor', 'w');
  subplot(2,1,2);
  plot(inl, 'Color', [0.97 0.32 0.29], 'LineWidth', 1.5);
  title('INL', 'Color', 'w'); xlabel('Code', 'Color', 'w'); ylabel('LSB', 'Color', 'w');
  yline(spec.inl_max_lsb, 'g--', 'LineWidth', 1.5);
  yline(-spec.inl_max_lsb, 'g--', 'LineWidth', 1.5);
  set(gca, 'Color', [0.1 0.1 0.13], 'XColor', 'w', 'YColor', 'w');
end


%% ============================================================================
%% VERA PLL Jitter Checker
%% ============================================================================
function results = vera_check_pll_jitter(ip_name, edge_times_ns, spec)
  results = {};
  periods = diff(edge_times_ns);
  jitter_rms_ps = std(periods) * 1000;   % ns → ps
  jitter_pk_ps  = (max(periods) - min(periods)) * 1000 / 2;

  fprintf('\n  PLL Jitter Results:\n');
  fprintf('    RMS Jitter = %.2f ps\n', jitter_rms_ps);
  fprintf('    Pk Jitter  = %.2f ps\n', jitter_pk_ps);

  ctx = sprintf('N_edges=%d mean_period=%.3fns', length(edge_times_ns), mean(periods));
  if isfield(spec, 'jitter_rms_ps')
    results{end+1} = vera_check_max(ip_name, 'vera_pll_jitter_rms', jitter_rms_ps, ...
      spec.jitter_rms_ps, 'ps_rms', 'pll_clkout', ctx);
  end
  if isfield(spec, 'jitter_pk_ps')
    results{end+1} = vera_check_max(ip_name, 'vera_pll_jitter_pk', jitter_pk_ps, ...
      spec.jitter_pk_ps, 'ps_pk', 'pll_clkout', ctx);
  end
end


%% ============================================================================
%% VERA Filter Frequency Response Checker
%% ============================================================================
function results = vera_check_filter_response(ip_name, H_mag_db, freqs_hz, spec)
  %% H_mag_db: magnitude response in dB at freqs_hz points
  %% spec: struct with passband_hz, stopband_hz, passband_ripple_db, stopband_atten_db
  results = {};

  if isfield(spec, 'passband_hz') && isfield(spec, 'passband_ripple_db')
    pb_mask    = freqs_hz <= spec.passband_hz;
    pb_ripple  = max(H_mag_db(pb_mask)) - min(H_mag_db(pb_mask));
    results{end+1} = vera_check_max(ip_name, 'vera_filter_pb_ripple', pb_ripple, ...
      spec.passband_ripple_db, 'dB', 'vout', ...
      sprintf('f<=%gHz', spec.passband_hz));
  end

  if isfield(spec, 'stopband_hz') && isfield(spec, 'stopband_atten_db')
    sb_mask   = freqs_hz >= spec.stopband_hz;
    sb_atten  = -max(H_mag_db(sb_mask));   % attenuation = negative gain
    results{end+1} = vera_check_min(ip_name, 'vera_filter_sb_atten', sb_atten, ...
      spec.stopband_atten_db, 'dB', 'vout', ...
      sprintf('f>=%gHz', spec.stopband_hz));
  end
end


%% ============================================================================
%% VERA Write Report — JSON output
%% ============================================================================
function vera_write_report(results_cell, output_path)
  pass_n = 0; fail_n = 0; warn_n = 0;
  for i = 1:length(results_cell)
    switch results_cell{i}.status
      case 'PASS',    pass_n = pass_n + 1;
      case 'FAIL',    fail_n = fail_n + 1;
      case 'WARNING', warn_n = warn_n + 1;
    end
  end

  fid = fopen(output_path, 'w');
  fprintf(fid, '{\n  "vera_report": {\n');
  fprintf(fid, '    "meta": {"checker_type": "matlab_postsim", "generated": "%s"},\n', ...
          datestr(now, 'yyyy-mm-ddTHH:MM:SS'));
  fprintf(fid, '    "summary": {"total": %d, "pass": %d, "fail": %d, "warning": %d},\n', ...
          length(results_cell), pass_n, fail_n, warn_n);
  fprintf(fid, '    "results": [\n');
  for i = 1:length(results_cell)
    r = results_cell{i};
    fprintf(fid, '      {"ip_name":"%s","checker_name":"%s","checker_type":"%s",', ...
            r.ip_name, r.checker_name, r.checker_type);
    fprintf(fid, '"status":"%s","severity":"%s","expected":"%s","actual":"%s",', ...
            r.status, r.severity, r.expected, r.actual);
    fprintf(fid, '"margin":"%s","context":"%s","debug_signal":"%s","recommendation":"%s"}', ...
            r.margin, r.context, r.debug_signal, r.recommendation);
    if i < length(results_cell), fprintf(fid, ','); end
    fprintf(fid, '\n');
  end
  fprintf(fid, '    ]\n  }\n}\n');
  fclose(fid);

  fprintf('\n  ============================================================\n');
  fprintf('  VERA MATLAB SUMMARY: PASS=%d FAIL=%d WARN=%d\n', pass_n, fail_n, warn_n);
  fprintf('  Report: %s\n', output_path);
  fprintf('  ============================================================\n\n');
end


%% ============================================================================
%% Helper: ternary operator
%% ============================================================================
function out = ternary(cond, a, b)
  if cond, out = a; else, out = b; end
end


%% ============================================================================
%% EXAMPLE USAGE (uncomment to run)
%% ============================================================================
%{
% Generate synthetic ADC data (12-bit, 1MSPS, 100kHz input)
N      = 4096;
n_bits = 12;
fs     = 1e6;
fin    = 97656;
t      = (0:N-1)/fs;
vin    = 0.9 + 0.85*sin(2*pi*fin*t);     % 0.9V center, 0.85V amplitude
codes  = round(vin / 1.8 * (2^n_bits - 1));
codes  = max(0, min(2^n_bits - 1, codes));

spec_dyn.enob_min    = 10.5;
spec_dyn.snr_min_db  = 65;
spec_dyn.sfdr_min_db = 75;
spec_dyn.thd_max_db  = -70;

spec_stat.dnl_max_lsb       = 0.5;
spec_stat.inl_max_lsb       = 1.0;
spec_stat.missing_codes_max = 0;

results = {};
r1 = vera_check_adc_dynamic('SAR_ADC_12B', codes, fs, fin, spec_dyn);
r2 = vera_check_adc_static('SAR_ADC_12B', codes, n_bits, spec_stat);
results = [results, r1, r2];

vera_write_report(results, 'vera_matlab_report.json');
%}
