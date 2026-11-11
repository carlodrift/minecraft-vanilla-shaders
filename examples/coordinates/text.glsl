#ifndef COORDINATES_TEXT_GLSL
#define COORDINATES_TEXT_GLSL

// The player's coordinates as a line of text, "x, y, z", in the game's own font, drawn by a post pass.
//
// Needs Globals and a FontSampler declared before this include: the game's font/ascii.png, copied into
// the pack as a post-effect texture by text.py. That PNG is a grid of 16 x 16 cells of 8 x 8 pixels,
// in ASCII order, the baseline under the 7th row.

const int TEXT_MAX = 40;   // characters in a line

const int CHAR_SPACE = 32;
const int CHAR_COMMA = 44;
const int CHAR_MINUS = 45;
const int CHAR_0 = 48;

struct TextLine {
    int chars[TEXT_MAX];
    int count;
};

void putChar(inout TextLine line, int c) {
    if (line.count < TEXT_MAX) {
        line.chars[line.count] = c;
        line.count++;
    }
}

void putInt(inout TextLine line, int value) {
    if (value < 0) {
        putChar(line, CHAR_MINUS);
        value = -value;
    }
    int digits[10];
    int n = 0;
    do {
        digits[n] = value % 10;
        value /= 10;
        n++;
    } while (value > 0 && n < 10);
    for (int i = n - 1; i >= 0; i--) {
        putChar(line, CHAR_0 + digits[i]);
    }
}

// Pixels a character moves the pen: its width in the font, plus one. Measured in the 26.3 ascii.png:
// 5 for the digits and the minus sign, 1 for the comma. The space is not in the PNG: 4 (font/include/space.json).
int charAdvance(int c) {
    if (c == CHAR_SPACE) {
        return 4;
    }
    return c == CHAR_COMMA ? 2 : 6;
}

// Width of a line in font pixels, without the spacing after its last character.
int lineWidth(TextLine line) {
    int width = 0;
    for (int i = 0; i < line.count; i++) {
        width += charAdvance(line.chars[i]);
    }
    return max(width - 1, 0);
}

// Whether the font pixel p of the line is set: p.x from the left of the line, p.y down from its top.
// Rows 0 to 6 are above the baseline, row 7 below it (the comma's tail).
bool lineInk(TextLine line, ivec2 p) {
    if (p.x < 0 || p.y < 0 || p.y >= 8) {
        return false;
    }
    int x = p.x;
    for (int i = 0; i < line.count; i++) {
        int c = line.chars[i];
        int advance = charAdvance(c);
        if (x < advance) {
            if (c == CHAR_SPACE || x == advance - 1) {
                return false;
            }
            // Texel row 0 is the PNG's top row.
            return texelFetch(FontSampler, ivec2((c & 15) * 8 + x, (c >> 4) * 8 + p.y), 0).a > 0.5;
        }
        x -= advance;
    }
    return false;
}

// The line at a screen pixel: (color, 1) on its text, (shadow, 1) on its shadow, 0 elsewhere. topLeft is
// the screen pixel at the top-left corner of the line (y up), scale the screen pixels per font pixel.
// The shadow is the game's: one font pixel right and down, at a quarter of the color.
vec4 drawLine(TextLine line, ivec2 pixel, ivec2 topLeft, int scale) {
    ivec2 d = ivec2(pixel.x - topLeft.x, topLeft.y - pixel.y);
    if (d.x < 0 || d.y < 0) {
        return vec4(0.0);
    }
    ivec2 p = d / scale;
    if (lineInk(line, p)) {
        return vec4(1.0);
    }
    if (lineInk(line, p - 1)) {
        return vec4(vec3(0.25), 1.0);
    }
    return vec4(0.0);
}

// The camera is at the eyes: 1.62 blocks above the feet when standing, flying or in spectator mode
// (Camera.alignWithEntity, in first person; 1.62 is the float the game uses).
const float EYE_HEIGHT = 1.62;

// The block the player's feet are in, as the debug screen's "Block:" line. CameraOffset is
// CameraBlockPos - camera, so -CameraOffset is the camera's fraction, in [0, 1).
ivec3 feetBlock() {
    float y = -CameraOffset.y - EYE_HEIGHT;
    // A hair under a whole number is float rounding of it: the feet on top of a block.
    return CameraBlockPos + ivec3(0, int(floor(y + 0.00001)), 0);
}

// "x, y, z" for the feet's block.
TextLine coordinatesLine() {
    ivec3 block = feetBlock();
    TextLine line;
    line.count = 0;
    putInt(line, block.x);
    putChar(line, CHAR_COMMA);
    putChar(line, CHAR_SPACE);
    putInt(line, block.y);
    putChar(line, CHAR_COMMA);
    putChar(line, CHAR_SPACE);
    putInt(line, block.z);
    return line;
}

// The GUI scale the game picks with the "Auto" option, from the window's size in pixels: the largest
// that leaves at least 320 x 240 GUI pixels (Window.calculateScale).
int autoGuiScale() {
    ivec2 size = ivec2(ScreenSize);
    return max(1, min(size.x / 320, size.y / 240));
}

#endif
