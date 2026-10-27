/* Isolated synthetic-key probe. No filesystem, network, environment key or CLI secret. */
'use strict';
const {createCipheriv, createDecipheriv, randomBytes} = require('node:crypto');
const chunks = [];
let length = 0;
process.stdin.on('data', chunk => {
  length += chunk.length;
  if (length > 96 * 1024 * 1024) process.exit(2);
  chunks.push(chunk);
});
process.stdin.on('end', () => {
  try {
    const input = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    if (input.syntheticOnly !== true) throw new Error();
    const key = Buffer.from(input.key, 'base64');
    const data = Buffer.from(input.data, 'base64');
    const aad = Buffer.from(input.aad, 'base64');
    if (key.length !== 32 || data.length > 64 * 1024 * 1024 || aad.length > 16384) throw new Error();
    let output;
    if (input.operation === 'seal') {
      const nonce = randomBytes(12);
      const cipher = createCipheriv('aes-256-gcm', key, nonce, {authTagLength: 16});
      cipher.setAAD(aad);
      const encrypted = Buffer.concat([cipher.update(data), cipher.final()]);
      output = Buffer.concat([nonce, cipher.getAuthTag(), encrypted]);
    } else if (input.operation === 'open') {
      if (data.length < 28) throw new Error();
      const decipher = createDecipheriv('aes-256-gcm', key, data.subarray(0, 12), {authTagLength: 16});
      decipher.setAAD(aad);
      decipher.setAuthTag(data.subarray(12, 28));
      // Do not release any plaintext until final() authenticates the whole message.
      output = Buffer.concat([decipher.update(data.subarray(28)), decipher.final()]);
    } else throw new Error();
    key.fill(0);
    process.stdout.write(output.toString('base64'));
  } catch {
    process.stderr.write('Synthetic cryptographic probe failed');
    process.exitCode = 2;
  }
});
