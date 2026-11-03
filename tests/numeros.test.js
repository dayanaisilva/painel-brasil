const assert = require('node:assert/strict');
const {lerValorBR} = require('../site/numeros.js');
for (const [input, expected] of [['1.000',1000],['1.000,00',1000],['0,50',.5],[' 12,34 ',12.34],['100abc',null],['1.2',null],['1,2,3',null],['Infinity',null],['-1',null],['0',null],['',null]]) {
  assert.equal(lerValorBR(input),expected,input);
}
console.log('11 casos de entrada monetária passaram.');
