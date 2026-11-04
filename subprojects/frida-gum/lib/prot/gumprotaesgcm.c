/*
 * Minimal, self-contained AES-256-GCM decryption for FPB1-protected agent
 * bytecode. GCM only needs the AES forward cipher (key expansion and
 * single-block encryption are used to generate the CTR-mode keystream and
 * the tag mask), so no inverse cipher is implemented. The forward cipher
 * below is a from-scratch implementation of the FIPS-197 algorithm.
 *
 * Licence: wxWindows Library Licence, Version 3.1
 */

#include "gumprotaesgcm.h"

#include <string.h>

#define GUM_PROT_AES_NK 8
#define GUM_PROT_AES_NR 14
#define GUM_PROT_AES_NB 4
#define GUM_PROT_AES_ROUND_KEY_SIZE \
    (GUM_PROT_AES_NB * (GUM_PROT_AES_NR + 1) * 4)
#define GUM_PROT_GCM_BLOCK_SIZE 16

typedef guint8 GumProtAesState[4][4];

static void gum_prot_aes256_expand_key (
    guint8 round_key[GUM_PROT_AES_ROUND_KEY_SIZE], const guint8 key[32]);
static void gum_prot_aes256_encrypt_block (
    const guint8 round_key[GUM_PROT_AES_ROUND_KEY_SIZE], guint8 block[16]);
static void gum_prot_aes256_add_round_key (guint8 round,
    GumProtAesState * state,
    const guint8 round_key[GUM_PROT_AES_ROUND_KEY_SIZE]);
static void gum_prot_aes256_sub_bytes (GumProtAesState * state);
static void gum_prot_aes256_shift_rows (GumProtAesState * state);
static void gum_prot_aes256_mix_columns (GumProtAesState * state);
static guint8 gum_prot_aes256_xtime (guint8 x);
static void gum_prot_gcm_mul (guint8 x[16], const guint8 y[16]);

static const guint8 gum_prot_aes_sbox[256] =
{
  0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
  0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
  0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
  0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
  0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
  0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
  0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
  0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
  0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
  0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
  0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
  0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
  0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
  0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
  0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
  0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
};

static const guint8 gum_prot_aes_rcon[11] =
{
  0x8d, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36
};

gboolean
gum_prot_aes256gcm_decrypt (const guint8 key[32],
                            const guint8 nonce[12],
                            const guint8 * ct,
                            gsize ct_len,
                            guint8 * out,
                            gsize * out_len)
{
  guint8 round_key[GUM_PROT_AES_ROUND_KEY_SIZE];
  guint8 h[16] = { 0, };
  guint8 j0[16];
  guint8 tag_state[16] = { 0, };
  guint8 counter[16];
  guint8 keystream[16];
  guint8 expected_tag[16];
  guint8 length_block[16] = { 0, };
  const guint8 * body;
  gsize body_len;
  guint64 body_bit_len;
  gsize i;
  guint8 diff;

  if (ct_len < GUM_PROT_GCM_BLOCK_SIZE)
    return FALSE;

  body = ct;
  body_len = ct_len - GUM_PROT_GCM_BLOCK_SIZE;

  gum_prot_aes256_expand_key (round_key, key);
  gum_prot_aes256_encrypt_block (round_key, h);

  memcpy (j0, nonce, 12);
  j0[12] = 0x00;
  j0[13] = 0x00;
  j0[14] = 0x00;
  j0[15] = 0x01;

  for (i = 0; i < body_len; i += GUM_PROT_GCM_BLOCK_SIZE)
  {
    guint8 block[16] = { 0, };
    gsize chunk = MIN (GUM_PROT_GCM_BLOCK_SIZE, body_len - i);
    gsize b;

    memcpy (block, body + i, chunk);
    for (b = 0; b != 16; b++)
      tag_state[b] ^= block[b];
    gum_prot_gcm_mul (tag_state, h);
  }

  body_bit_len = (guint64) body_len * 8;
  for (i = 0; i != 8; i++)
    length_block[8 + i] = (guint8) (body_bit_len >> (56 - i * 8));
  for (i = 0; i != 16; i++)
    tag_state[i] ^= length_block[i];
  gum_prot_gcm_mul (tag_state, h);

  memcpy (counter, j0, 16);
  gum_prot_aes256_encrypt_block (round_key, counter);
  for (i = 0; i != 16; i++)
    expected_tag[i] = tag_state[i] ^ counter[i];

  diff = 0;
  for (i = 0; i != 16; i++)
    diff |= expected_tag[i] ^ body[body_len + i];
  if (diff != 0)
    return FALSE;

  memcpy (counter, j0, 16);
  for (i = 0; i < body_len; i += GUM_PROT_GCM_BLOCK_SIZE)
  {
    gsize chunk = MIN (GUM_PROT_GCM_BLOCK_SIZE, body_len - i);
    gsize b;

    for (b = 16; b != 12; b--)
    {
      if (++counter[b - 1] != 0)
        break;
    }

    memcpy (keystream, counter, 16);
    gum_prot_aes256_encrypt_block (round_key, keystream);

    for (b = 0; b != chunk; b++)
      out[i + b] = body[i + b] ^ keystream[b];
  }

  *out_len = body_len;

  return TRUE;
}

static void
gum_prot_aes256_expand_key (guint8 round_key[GUM_PROT_AES_ROUND_KEY_SIZE],
                            const guint8 key[32])
{
  guint i, j, k;
  guint8 tempa[4];

  for (i = 0; i != GUM_PROT_AES_NK; i++)
  {
    round_key[(i * 4) + 0] = key[(i * 4) + 0];
    round_key[(i * 4) + 1] = key[(i * 4) + 1];
    round_key[(i * 4) + 2] = key[(i * 4) + 2];
    round_key[(i * 4) + 3] = key[(i * 4) + 3];
  }

  for (i = GUM_PROT_AES_NK; i != GUM_PROT_AES_NB * (GUM_PROT_AES_NR + 1); i++)
  {
    k = (i - 1) * 4;
    tempa[0] = round_key[k + 0];
    tempa[1] = round_key[k + 1];
    tempa[2] = round_key[k + 2];
    tempa[3] = round_key[k + 3];

    if (i % GUM_PROT_AES_NK == 0)
    {
      guint8 tmp = tempa[0];

      tempa[0] = gum_prot_aes_sbox[tempa[1]];
      tempa[1] = gum_prot_aes_sbox[tempa[2]];
      tempa[2] = gum_prot_aes_sbox[tempa[3]];
      tempa[3] = gum_prot_aes_sbox[tmp];

      tempa[0] ^= gum_prot_aes_rcon[i / GUM_PROT_AES_NK];
    }
    else if (i % GUM_PROT_AES_NK == 4)
    {
      tempa[0] = gum_prot_aes_sbox[tempa[0]];
      tempa[1] = gum_prot_aes_sbox[tempa[1]];
      tempa[2] = gum_prot_aes_sbox[tempa[2]];
      tempa[3] = gum_prot_aes_sbox[tempa[3]];
    }

    j = i * 4;
    k = (i - GUM_PROT_AES_NK) * 4;
    round_key[j + 0] = round_key[k + 0] ^ tempa[0];
    round_key[j + 1] = round_key[k + 1] ^ tempa[1];
    round_key[j + 2] = round_key[k + 2] ^ tempa[2];
    round_key[j + 3] = round_key[k + 3] ^ tempa[3];
  }
}

static void
gum_prot_aes256_encrypt_block (const guint8 round_key[GUM_PROT_AES_ROUND_KEY_SIZE],
                               guint8 block[16])
{
  GumProtAesState * state = (GumProtAesState *) block;
  guint8 round;

  gum_prot_aes256_add_round_key (0, state, round_key);

  for (round = 1; ; round++)
  {
    gum_prot_aes256_sub_bytes (state);
    gum_prot_aes256_shift_rows (state);
    if (round == GUM_PROT_AES_NR)
      break;
    gum_prot_aes256_mix_columns (state);
    gum_prot_aes256_add_round_key (round, state, round_key);
  }

  gum_prot_aes256_add_round_key (GUM_PROT_AES_NR, state, round_key);
}

static void
gum_prot_aes256_add_round_key (guint8 round,
                               GumProtAesState * state,
                               const guint8 round_key[GUM_PROT_AES_ROUND_KEY_SIZE])
{
  guint8 i, j;

  for (i = 0; i != 4; i++)
  {
    for (j = 0; j != 4; j++)
    {
      (*state)[i][j] ^=
          round_key[(round * GUM_PROT_AES_NB * 4) + (i * GUM_PROT_AES_NB) + j];
    }
  }
}

static void
gum_prot_aes256_sub_bytes (GumProtAesState * state)
{
  guint8 i, j;

  for (i = 0; i != 4; i++)
  {
    for (j = 0; j != 4; j++)
      (*state)[j][i] = gum_prot_aes_sbox[(*state)[j][i]];
  }
}

static void
gum_prot_aes256_shift_rows (GumProtAesState * state)
{
  guint8 temp;

  temp = (*state)[0][1];
  (*state)[0][1] = (*state)[1][1];
  (*state)[1][1] = (*state)[2][1];
  (*state)[2][1] = (*state)[3][1];
  (*state)[3][1] = temp;

  temp = (*state)[0][2];
  (*state)[0][2] = (*state)[2][2];
  (*state)[2][2] = temp;
  temp = (*state)[1][2];
  (*state)[1][2] = (*state)[3][2];
  (*state)[3][2] = temp;

  temp = (*state)[0][3];
  (*state)[0][3] = (*state)[3][3];
  (*state)[3][3] = (*state)[2][3];
  (*state)[2][3] = (*state)[1][3];
  (*state)[1][3] = temp;
}

static guint8
gum_prot_aes256_xtime (guint8 x)
{
  return (guint8) ((x << 1) ^ (((x >> 7) & 1) * 0x1b));
}

static void
gum_prot_aes256_mix_columns (GumProtAesState * state)
{
  guint8 i;

  for (i = 0; i != 4; i++)
  {
    guint8 a0 = (*state)[i][0];
    guint8 a1 = (*state)[i][1];
    guint8 a2 = (*state)[i][2];
    guint8 a3 = (*state)[i][3];
    guint8 sum = a0 ^ a1 ^ a2 ^ a3;

    (*state)[i][0] ^= sum ^ gum_prot_aes256_xtime (a0 ^ a1);
    (*state)[i][1] ^= sum ^ gum_prot_aes256_xtime (a1 ^ a2);
    (*state)[i][2] ^= sum ^ gum_prot_aes256_xtime (a2 ^ a3);
    (*state)[i][3] ^= sum ^ gum_prot_aes256_xtime (a3 ^ a0);
  }
}

static void
gum_prot_gcm_mul (guint8 x[16],
                  const guint8 y[16])
{
  guint8 z[16] = { 0, };
  guint8 v[16];
  gint i, j;

  memcpy (v, y, 16);

  for (i = 0; i != 16; i++)
  {
    for (j = 0; j != 8; j++)
    {
      gint k;
      guint8 carry_in;

      if ((x[i] >> (7 - j)) & 1)
      {
        for (k = 0; k != 16; k++)
          z[k] ^= v[k];
      }

      carry_in = v[15] & 1;
      for (k = 15; k != 0; k--)
        v[k] = (v[k] >> 1) | ((v[k - 1] & 1) << 7);
      v[0] >>= 1;
      if (carry_in)
        v[0] ^= 0xe1;
    }
  }

  memcpy (x, z, 16);
}
