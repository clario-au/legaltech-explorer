/* filter_utils.js
 * Pure helpers for matching tool records against filter selections.
 * Loaded as a classic script by index.html (functions become globals) and
 * required by tests/filter_utils.test.js under Node.
 */

/* Split a multi-value field. Separators are ; , | and newlines.
 * "/" is deliberately NOT a separator: it is part of many canonical values
 * ("Government / Public Sector", "Natural Language Processing (NLP) / Text Analytics"). */
function splitMulti(v){
  if(!v) return [];
  return String(v).split(/[;,|\n]+/)
    .map(function(x){ return x.trim(); })
    .map(function(x){ return x.replace(/^and\s+/i, ''); })   // Remove leading "and "
    .filter(function(x){ return x && x.toLowerCase() !== 'and'; });
}

/* Normalise a value for comparison: case-insensitive, ignore trailing full stops. */
function normalizeFilterValue(v){
  return String(v == null ? '' : v).replace(/\.+$/, '').trim().toLowerCase();
}

/* A "Global" region tag means the vendor serves every region. */
function isGlobalRegion(v){
  return /^global\b/i.test(String(v || '').trim());
}

function multiMatch(recVal, selected, fieldKey){
  if(!selected || !selected.length) return true;
  var hay = splitMulti(recVal);

  if(fieldKey === 'Regions Served'){
    // No region data: treat as available everywhere (don't filter it out)
    if(hay.length === 0) return true;
    if(hay.some(isGlobalRegion)) return true;
  }

  var set = {};
  hay.forEach(function(v){ set[normalizeFilterValue(v)] = 1; });
  for(var i = 0; i < selected.length; i++){
    if(set[normalizeFilterValue(selected[i])]) return true;
  }
  return false;
}

if(typeof module !== 'undefined' && module.exports){
  module.exports = { splitMulti: splitMulti, normalizeFilterValue: normalizeFilterValue, isGlobalRegion: isGlobalRegion, multiMatch: multiMatch };
}
