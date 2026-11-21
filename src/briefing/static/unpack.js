/* briefing unpack (#38): data a report stores compressed, unpacked as the report opens.

   window.briefingUnpack(base64, size) returns the text that Python packed with
   briefing.renderers.pack: UTF-8, compressed as raw DEFLATE (RFC 1951), base64-encoded;
   *size* is its length in bytes once inflated. It is synchronous and needs no browser API
   beyond typed arrays, so a report can unpack a chart runtime in <head>, before the
   charts below it are drawn. The decoder follows zlib's puff.c. This file defines a
   function and touches no element: it is not a part. */
(function () {
  'use strict';
  if (window.briefingUnpack) return;

  var LENGTH_BASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115,
                     131, 163, 195, 227, 258];
  var LENGTH_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0];
  var DIST_BASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537,
                   2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577];
  var DIST_EXTRA = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13];
  var CODE_LENGTH_ORDER = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15];

  // A canonical Huffman code: how many codes have each length, and the symbols in code order.
  function huffman(lengths, n) {
    var counts = new Uint16Array(16), symbols = new Uint16Array(n), offsets = new Uint16Array(16), i;
    for (i = 0; i < n; i++) counts[lengths[i]]++;
    counts[0] = 0;
    for (i = 1; i < 16; i++) offsets[i] = offsets[i - 1] + counts[i - 1];
    for (i = 0; i < n; i++) if (lengths[i]) symbols[offsets[lengths[i]]++] = i;
    return { counts: counts, symbols: symbols };
  }

  var fixedLengths = null, fixedDistances = null;

  function fail(why) { throw new Error('briefing: the compressed data is damaged (' + why + ')'); }

  function inflate(input, size) {
    var output = new Uint8Array(size), out = 0, at = 0, bitBuffer = 0, bitCount = 0;

    function bits(need) {
      var value = bitBuffer;
      while (bitCount < need) {
        if (at >= input.length) fail('it ends early');
        value |= input[at++] << bitCount;
        bitCount += 8;
      }
      bitBuffer = value >>> need;
      bitCount -= need;
      return value & ((1 << need) - 1);
    }

    function decode(code) {
      var bitsSoFar = 0, first = 0, index = 0, length, count;
      for (length = 1; length < 16; length++) {
        if (bitCount === 0) {
          if (at >= input.length) fail('it ends early');
          bitBuffer = input[at++];
          bitCount = 8;
        }
        bitsSoFar |= bitBuffer & 1;
        bitBuffer >>>= 1;
        bitCount--;
        count = code.counts[length];
        if (bitsSoFar - count < first) return code.symbols[index + (bitsSoFar - first)];
        index += count;
        first = (first + count) << 1;
        bitsSoFar <<= 1;
      }
      return fail('a code is too long');
    }

    function stored() {
      bitBuffer = 0;
      bitCount = 0;
      if (at + 4 > input.length) fail('it ends early');
      var length = input[at] | (input[at + 1] << 8);
      var check = input[at + 2] | (input[at + 3] << 8);
      at += 4;
      if (length !== (~check & 0xffff)) fail('a stored length');
      if (at + length > input.length || out + length > size) fail('a stored block');
      output.set(input.subarray(at, at + length), out);
      at += length;
      out += length;
    }

    function codes(lengthCode, distanceCode) {
      var symbol, length, distance;
      for (;;) {
        symbol = decode(lengthCode);
        if (symbol < 256) {
          if (out >= size) fail('too much data');
          output[out++] = symbol;
        } else if (symbol === 256) {
          return;
        } else {
          symbol -= 257;
          if (symbol >= 29) fail('a length');
          length = LENGTH_BASE[symbol] + bits(LENGTH_EXTRA[symbol]);
          symbol = decode(distanceCode);
          if (symbol >= 30) fail('a distance');
          distance = DIST_BASE[symbol] + bits(DIST_EXTRA[symbol]);
          if (distance > out || out + length > size) fail('a copy');
          while (length--) { output[out] = output[out - distance]; out++; }
        }
      }
    }

    function fixed() {
      if (!fixedLengths) {
        var lengths = new Uint8Array(288), i;
        for (i = 0; i < 144; i++) lengths[i] = 8;
        for (; i < 256; i++) lengths[i] = 9;
        for (; i < 280; i++) lengths[i] = 7;
        for (; i < 288; i++) lengths[i] = 8;
        fixedLengths = huffman(lengths, 288);
        var distances = new Uint8Array(30);
        for (i = 0; i < 30; i++) distances[i] = 5;
        fixedDistances = huffman(distances, 30);
      }
      codes(fixedLengths, fixedDistances);
    }

    function dynamic() {
      var lengthCount = bits(5) + 257, distanceCount = bits(5) + 1, codeCount = bits(4) + 4;
      var lengths = new Uint8Array(19), i, symbol, repeat, value;
      if (lengthCount > 286 || distanceCount > 30) fail('too many codes');
      for (i = 0; i < codeCount; i++) lengths[CODE_LENGTH_ORDER[i]] = bits(3);
      var codeLengthCode = huffman(lengths, 19);
      var all = lengthCount + distanceCount;
      lengths = new Uint8Array(all);
      i = 0;
      while (i < all) {
        symbol = decode(codeLengthCode);
        if (symbol < 16) {
          lengths[i++] = symbol;
        } else {
          value = 0;
          if (symbol === 16) {
            if (i === 0) fail('a repeat with nothing before it');
            value = lengths[i - 1];
            repeat = 3 + bits(2);
          } else if (symbol === 17) {
            repeat = 3 + bits(3);
          } else {
            repeat = 11 + bits(7);
          }
          if (i + repeat > all) fail('a repeat');
          while (repeat--) lengths[i++] = value;
        }
      }
      codes(huffman(lengths.subarray(0, lengthCount), lengthCount),
            huffman(lengths.subarray(lengthCount), distanceCount));
    }

    var last, type;
    do {
      last = bits(1);
      type = bits(2);
      if (type === 0) stored();
      else if (type === 1) fixed();
      else if (type === 2) dynamic();
      else fail('a block type');
    } while (!last);
    if (out !== size) fail('unpacked ' + out + ' bytes, not ' + size);
    return output;
  }

  function utf8(bytes) {
    // ignoreBOM keeps a leading byte-order mark, which a CSV for spreadsheets needs (#36).
    if (typeof TextDecoder !== 'undefined') return new TextDecoder('utf-8', { ignoreBOM: true }).decode(bytes);
    var text = '', i, step = 8192;
    for (i = 0; i < bytes.length; i += step) text += String.fromCharCode.apply(null, bytes.subarray(i, i + step));
    return decodeURIComponent(escape(text));
  }

  window.briefingUnpack = function (base64, size) {
    var binary = atob(base64), input = new Uint8Array(binary.length), i;
    for (i = 0; i < binary.length; i++) input[i] = binary.charCodeAt(i);
    return utf8(inflate(input, size));
  };
})();
