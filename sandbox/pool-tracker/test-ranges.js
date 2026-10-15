// test-ranges.js
// Run with:  node test-ranges.js
// Uses only node's built-in assert module, so there is nothing to install.

var assert = require('assert');
var PoolRanges = require('./ranges.js');

var passed = 0;
var failed = 0;

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log('  ok    ' + name);
  } catch (err) {
    failed++;
    console.log('  FAIL  ' + name);
    console.log('        ' + err.message);
  }
}

var phRange = { min: 7.2, max: 7.8 };

test('a value inside the range is ok', function () {
  assert.strictEqual(PoolRanges.checkValue(7.5, phRange), 'ok');
});

test('the exact min and max count as ok', function () {
  assert.strictEqual(PoolRanges.checkValue(7.2, phRange), 'ok');
  assert.strictEqual(PoolRanges.checkValue(7.8, phRange), 'ok');
});

test('a value below the range is low', function () {
  assert.strictEqual(PoolRanges.checkValue(7.0, phRange), 'low');
});

test('a value above the range is high', function () {
  assert.strictEqual(PoolRanges.checkValue(8.1, phRange), 'high');
});

test('a blank or non-numeric value is missing, not flagged', function () {
  assert.strictEqual(PoolRanges.checkValue('', phRange), 'missing');
  assert.strictEqual(PoolRanges.checkValue(null, phRange), 'missing');
  assert.strictEqual(PoolRanges.checkValue('abc', phRange), 'missing');
});

test('numbers stored as text are still checked', function () {
  assert.strictEqual(PoolRanges.checkValue('8.1', phRange), 'high');
});

test('checkEntry checks every field using the default ranges', function () {
  var entry = { date: '2026-10-15', fc: 0.5, ph: 7.4, ta: 150, cya: 40, ch: '', temp: 80 };
  var result = PoolRanges.checkEntry(entry, PoolRanges.defaultRanges());
  assert.deepStrictEqual(result, {
    fc: 'low', ph: 'ok', ta: 'high', cya: 'ok', ch: 'missing', temp: 'ok'
  });
});

test('defaultRanges returns a new copy each time', function () {
  var a = PoolRanges.defaultRanges();
  a.ph.min = 0;
  assert.strictEqual(PoolRanges.defaultRanges().ph.min, 7.2);
});

test('validateRange rejects min greater than max and non-numbers', function () {
  assert.strictEqual(PoolRanges.validateRange({ min: 1, max: 4 }), null);
  assert.ok(PoolRanges.validateRange({ min: 5, max: 4 }));
  assert.ok(PoolRanges.validateRange({ min: NaN, max: 4 }));
});

console.log('\n' + passed + ' passed, ' + failed + ' failed');
if (failed > 0) process.exit(1);
