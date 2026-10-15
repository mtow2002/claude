// ranges.js
// The range-check logic for the pool tracker, kept separate from the page
// so it can be tested with plain node (see test-ranges.js).
// It works in two places:
//   1. In the browser, index.html loads it with a <script> tag and uses window.PoolRanges.
//   2. In node, test-ranges.js loads it with require('./ranges.js').

(function (root) {
  // Each reading the page tracks, in the order shown on screen.
  // The min and max values are general starting points, not rules for your pool.
  var FIELDS = [
    { key: 'fc',   label: 'Free chlorine',      unit: 'ppm', min: 1,   max: 4 },
    { key: 'ph',   label: 'pH',                 unit: '',    min: 7.2, max: 7.8 },
    { key: 'ta',   label: 'Total alkalinity',   unit: 'ppm', min: 80,  max: 120 },
    { key: 'cya',  label: 'Cyanuric acid',      unit: 'ppm', min: 30,  max: 50 },
    { key: 'ch',   label: 'Calcium hardness',   unit: 'ppm', min: 200, max: 400 },
    { key: 'temp', label: 'Water temperature',  unit: '°F',  min: 78,  max: 86 }
  ];

  // Returns a fresh copy of the default ranges, shaped like { fc: { min: 1, max: 4 }, ... }.
  function defaultRanges() {
    var ranges = {};
    FIELDS.forEach(function (f) {
      ranges[f.key] = { min: f.min, max: f.max };
    });
    return ranges;
  }

  // Checks one value against one range.
  // Returns 'missing' if there is no number, 'low' or 'high' if it is outside, otherwise 'ok'.
  // The min and max themselves count as inside the range.
  function checkValue(value, range) {
    if (value === null || value === undefined || value === '') return 'missing';
    var n = Number(value);
    if (!Number.isFinite(n)) return 'missing';
    if (!range) return 'ok';
    if (range.min !== null && range.min !== undefined && n < range.min) return 'low';
    if (range.max !== null && range.max !== undefined && n > range.max) return 'high';
    return 'ok';
  }

  // Checks every reading in one entry.
  // Returns an object such as { fc: 'ok', ph: 'high', ... }.
  function checkEntry(entry, ranges) {
    var result = {};
    FIELDS.forEach(function (f) {
      result[f.key] = checkValue(entry[f.key], ranges[f.key]);
    });
    return result;
  }

  // Makes sure a range from the settings form is usable.
  // Returns an error message, or null if the range is fine.
  function validateRange(range) {
    if (!Number.isFinite(range.min) || !Number.isFinite(range.max)) {
      return 'Min and max must both be numbers.';
    }
    if (range.min > range.max) return 'Min must not be greater than max.';
    return null;
  }

  var api = {
    FIELDS: FIELDS,
    defaultRanges: defaultRanges,
    checkValue: checkValue,
    checkEntry: checkEntry,
    validateRange: validateRange
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;      // node
  } else {
    root.PoolRanges = api;     // browser
  }
})(this);
