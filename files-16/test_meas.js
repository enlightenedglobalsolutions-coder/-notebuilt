const M = require('./meas_widget.js');
let p=0,f=0; const ok=(n,c,x)=>{ c?(p++,console.log("  PASS "+n)):(f++,console.log("  FAIL "+n+" ["+x+"]")); };

// --- imperial round-trips ---
let w = M.inchesToImperial(262.25);
ok("262.25 -> 21ft 10in 1/4", w.ft===21&&w.in===10&&w.frac==="1/4", JSON.stringify(w));
ok("imperial back: 21,10,1/4 -> 262.25", Math.abs(M.imperialToInches(21,10,"1/4")-262.25)<.001, M.imperialToInches(21,10,"1/4"));
ok("96 -> 8ft 0 0", (()=>{let x=M.inchesToImperial(96);return x.ft===8&&x.in===0&&x.frac==="";})());
ok("0.75 -> 0ft 0in 3/4", (()=>{let x=M.inchesToImperial(0.75);return x.ft===0&&x.in===0&&x.frac==="3/4";})());
ok("empty fraction ok: 5,6,'' -> 66", Math.abs(M.imperialToInches(5,6,"")-66)<.001);
ok("blank ft: '',10,1/2 -> 10.5", Math.abs(M.imperialToInches("",10,"1/2")-10.5)<.001);
ok("bad fraction -> null", M.imperialToInches(5,0,"abc")===null);

// --- metric round-trips ---
ok("metric 6401mm-ish: 252in -> 6.4008m", (()=>{let x=M.inchesToMetric(252);return x.m===6&&Math.abs(x.cm-40.08)<.5;})());
ok("metric back: 6m 40cm -> ~251.97in", Math.abs(M.metricToInches(6,40)-251.97)<.5, M.metricToInches(6,40));
ok("metric 1m -> 39.37in", Math.abs(M.metricToInches(1,0)-39.3701)<.01, M.metricToInches(1,0));
ok("cm rollover: 6m 100cm normalizes", (()=>{let x=M.inchesToMetric(M.metricToInches(6,100));return x.m===7&&x.cm<1;})());

// --- widget HTML render ---
let hi = M.measWidget("test", 262.25, "imperial");
ok("imperial widget has 3 boxes", (hi.match(/data-meas-(ft|in|frac)/g)||[]).length===3);
ok("imperial widget prefilled 21/10/1/4", hi.includes('value="21"')&&hi.includes('value="10"')&&hi.includes('value="1/4"'));
let hm = M.measWidget("test", 252, "metric");
ok("metric widget has 2 boxes", (hm.match(/data-meas-(m|cm)/g)||[]).length===2);

// --- measRead via a fake DOM ---
function fakeRoot(mode, vals){
  return { getAttribute:()=>mode, querySelector:(sel)=>{
    for(const k in vals){ if(sel.includes(k)) return {value:vals[k]}; } return {value:""}; } };
}
ok("read imperial 21/10/1/4 -> 262.25", Math.abs(M.measRead(fakeRoot("imperial",{"meas-ft":"21","meas-in":"10","meas-frac":"1/4"}))-262.25)<.001);
ok("read metric 6/40 -> ~251.97", Math.abs(M.measRead(fakeRoot("metric",{"meas-m":"6","meas-cm":"40"}))-251.97)<.5);
ok("read all-blank imperial -> null", M.measRead(fakeRoot("imperial",{}))===null);

// --- echo cross-check ---
ok("imperial echo shows mm", M.measEcho(252,"imperial").includes("mm"));
ok("metric echo shows imperial", M.measEcho(252,"metric").includes("imperial"));

// --- the critical invariant: round-trip inches->widget->read is lossless to 1/16 ---
[262.25, 96, 0.75, 144.5, 5.5, 190.0625].forEach(v=>{
  let x = M.inchesToImperial(v);
  let back = M.imperialToInches(x.ft, x.in, x.frac);
  ok("imperial round-trip "+v, Math.abs(back-v)<0.0626, back);
});

console.log("\n"+p+" passed, "+f+" failed"); process.exit(f?1:0);
