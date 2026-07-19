// ============================================================================
//  EGS Measurement Widget — shared across Notebuilt + Stagger
//  Stores INCHES internally (all engines speak inches). The unit mode only
//  changes how the boxes render and how we read them back. Nothing downstream
//  ever sees anything but inches.
//
//  Imperial: three boxes  ft | in | fraction(typed, e.g. 1/4)
//  Metric:   two boxes     m  | cm
//  Unit mode: global default (settings.units) + optional per-field override.
// ============================================================================

var MEAS_MODE_DEFAULT = "imperial";  // host overrides from settings

// ---- conversions (inch is the canonical unit) ----
function inchesToImperial(inches){
  var neg = inches < 0; inches = Math.abs(inches);
  var totalSix = Math.round(inches * 16);
  var ft = Math.floor(totalSix / (12*16)); totalSix -= ft*12*16;
  var inch = Math.floor(totalSix / 16); var fr = totalSix - inch*16;
  var fracStr = "";
  if (fr > 0){ var n=fr, d=16; while(n%2===0 && d>1){ n/=2; d/=2; } fracStr = n + "/" + d; }
  return { ft: (neg?-ft:ft), in: inch, frac: fracStr };
}
function imperialToInches(ftStr, inStr, fracStr){
  var ft = parseFloat(ftStr); if (isNaN(ft)) ft = 0;
  var inch = parseFloat(inStr); if (isNaN(inch)) inch = 0;
  var frac = 0;
  if (fracStr && String(fracStr).trim()){
    var m = String(fracStr).trim().match(/^(\d+)\s*\/\s*(\d+)$/);
    if (m){ var dd=+m[2]; if(!dd) return null; frac = (+m[1])/dd; }
    else if (/^\d*\.?\d+$/.test(fracStr.trim())) { frac = parseFloat(fracStr); } // tolerate a decimal
    else return null; // unreadable fraction
  }
  var sign = ft < 0 ? -1 : 1;
  return sign * (Math.abs(ft)*12 + inch + frac);
}
var MM_PER_INCH = 25.4;
function inchesToMetric(inches){
  var mm = inches * MM_PER_INCH;
  var m = Math.floor(mm / 1000);
  var cm = Math.round((mm - m*1000) / 10 * 10) / 10;  // cm to 1 decimal
  if (cm >= 100){ m += 1; cm -= 100; }
  return { m: m, cm: cm };
}
function metricToInches(mStr, cmStr){
  var m = parseFloat(mStr); if (isNaN(m)) m = 0;
  var cm = parseFloat(cmStr); if (isNaN(cm)) cm = 0;
  var mm = m*1000 + cm*10;
  return mm / MM_PER_INCH;
}

// ---- read a widget's DOM back to inches (null if unreadable) ----
function measRead(rootEl){
  var mode = rootEl.getAttribute("data-mode") || MEAS_MODE_DEFAULT;
  if (mode === "metric"){
    var m = rootEl.querySelector('[data-meas-m]').value;
    var cm = rootEl.querySelector('[data-meas-cm]').value;
    if (String(m).trim()==="" && String(cm).trim()==="") return null;
    return metricToInches(m, cm);
  } else {
    var ft = rootEl.querySelector('[data-meas-ft]').value;
    var inch = rootEl.querySelector('[data-meas-in]').value;
    var frac = rootEl.querySelector('[data-meas-frac]').value;
    if (String(ft).trim()==="" && String(inch).trim()==="" && String(frac).trim()==="") return null;
    return imperialToInches(ft, inch, frac);
  }
}

// ---- render a widget (returns HTML string). id must be unique on screen. ----
function measWidget(id, inches, mode){
  mode = mode || MEAS_MODE_DEFAULT;
  var box = 'class="input meas-box" inputmode="decimal" autocomplete="off"';
  if (mode === "metric"){
    var v = (inches!=null) ? inchesToMetric(inches) : {m:"",cm:""};
    return '<div class="meas" data-meas="'+id+'" data-mode="metric">'
      + '<span class="meas-cell"><input '+box+' data-meas-m value="'+v.m+'" placeholder="0"><label>m</label></span>'
      + '<span class="meas-cell"><input '+box+' data-meas-cm value="'+v.cm+'" placeholder="0"><label>cm</label></span>'
      + '</div>';
  } else {
    var w = (inches!=null) ? inchesToImperial(inches) : {ft:"",in:"",frac:""};
    return '<div class="meas" data-meas="'+id+'" data-mode="imperial">'
      + '<span class="meas-cell"><input '+box+' data-meas-ft value="'+w.ft+'" placeholder="0"><label>ft</label></span>'
      + '<span class="meas-cell"><input '+box+' data-meas-in value="'+w.in+'" placeholder="0"><label>in</label></span>'
      + '<span class="meas-cell"><input class="input meas-box" autocomplete="off" data-meas-frac value="'+w.frac+'" placeholder="0"><label>frac</label></span>'
      + '</div>';
  }
}

// ---- the echo string (what the value reads as, in the OTHER unit for cross-check) ----
function measEcho(inches, mode){
  if (inches==null) return "";
  mode = mode || MEAS_MODE_DEFAULT;
  if (mode === "metric"){
    var w = inchesToImperial(inches);
    var s = (w.ft?w.ft+"'-":"") + w.in + (w.frac?" "+w.frac:"") + '"';
    return "= " + s + " imperial";
  } else {
    var mm = Math.round(inches*MM_PER_INCH);
    return "= " + mm + " mm";
  }
}

if (typeof module !== "undefined") module.exports = {
  inchesToImperial, imperialToInches, inchesToMetric, metricToInches,
  measRead, measWidget, measEcho
};
