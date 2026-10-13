import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/scoreThreshold.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022,
} }).outputText
const { thresholdFromPointer, thresholdFromKey } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)

test('each of six rail points maps to its aligned score row', () => {
  for (let index = 0; index < 6; index++) {
    assert.equal(thresholdFromPointer(100 + index * 52, 100, 260), 5 - index)
  }
})
test('dragging snaps to a point and clamps outside the rail', () => {
  assert.equal(thresholdFromPointer(199, 100, 260), 3)
  assert.equal(thresholdFromPointer(-500, 100, 260), 5)
  assert.equal(thresholdFromPointer(900, 100, 260), 0)
})
test('keyboard changes honor vertical direction and score bounds', () => {
  assert.equal(thresholdFromKey(3, 'ArrowUp'), 4)
  assert.equal(thresholdFromKey(3, 'ArrowDown'), 2)
  assert.equal(thresholdFromKey(5, 'ArrowRight'), 5)
  assert.equal(thresholdFromKey(0, 'ArrowLeft'), 0)
  assert.equal(thresholdFromKey(3, 'Home'), 0)
  assert.equal(thresholdFromKey(3, 'End'), 5)
  assert.equal(thresholdFromKey(3, 'Tab'), null)
})
