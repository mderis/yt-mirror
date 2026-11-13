/**
 * Loads every bundled font. Implements R-TH-05.
 *
 * Each folder here holds one font: its files, its license and a font.css that
 * declares it. Every font.css is picked up automatically, so adding a font
 * needs no change in this file. Which font the app uses is decided by the
 * --ytm-font-* tokens in ../tokens.css.
 */
import.meta.glob('./*/font.css', { eager: true })
