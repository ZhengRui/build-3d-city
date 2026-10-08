// Roofs (06_tiles' roof code in TEXCOORD_2.y = rise + 8 x material, uvRange.base[1]; facade.roofs; styles.js roof):
// flat roofs in the city's tones, villages' dark roofs, factories' steel, zinc and slate (London's: slate everywhere,
// roofs.slate), clay tile, Paris's roofscape variety, Berlin's flat tops, a mansard's brisis with its dormers. One
// implementation for every city, its choices the city's data; the facade (facade.js) passes the nodes it shares.
import { vec3, mix, smoothstep, max, min, floor, fwidth, hash, positionWorld } from 'three/tsl';
const { float, f01, sel, stripe, h1, hash2 } = await import(`./core.js${new URL(import.meta.url).search}`);

// c: the facade's nodes (seed, height, y, s, X, fx, col, fyM, wallH, wallColor, hasRoof, roofMat, roofRise, roofCodes,
// brisis, the style tests isFactory, isVillage, isSpire, isMon, and slateMetal (roof.metal slate), flatStyles
// (roof.flat), dormersEvery (roof.dormers every), NONE). Returns the roof's and the slopes' colours, whether it is zinc
// and whether a factory's is blue steel (for the roughness)
export function roofLook(c, roofs = {}) {
  const { seed, height, y, s, X, fx, col, fyM, wallH, wallColor, hasRoof, roofMat, roofRise, roofCodes, brisis, isFactory,
    isVillage, isSpire, isMon, slateMetal, flatStyles, dormersEvery, NONE } = c;
    // ---- roofs: one tone per building from the city's list (facade.roofs.tones, linear, [colour, weight]:
    // concrete by default; New York's tar, silver coating, white membrane, gravel), darker in villages, blue
    // (a share, facade.roofs.blueSteel; its colour facade.roofs.blueTone, linear) or grey steel on factories
    const rx = floor(positionWorld.x.div(1.5)), rz = floor(positionWorld.z.div(1.5));
    const roofNoise = hash2(rx, rz).sub(0.5).mul(0.025);
    const blueSteel = h1(seed.mul(7.7)).lessThan(roofs.blueSteel ?? 0.45);
    const tones = roofs.tones ?? [[[0.3, 0.3, 0.29], 1]];
    const toneTotal = tones.reduce((a, [, w]) => a + w, 0);
    const toneH = h1(seed.mul(61.3));
    let roofTone = vec3(...tones[0][0]), acc = tones[0][1];
    for (const [c, w] of tones.slice(1)) { roofTone = mix(roofTone, vec3(...c), f01(toneH.greaterThan(acc / toneTotal))); acc += w; }
    // Paris's roofs by material (06_tiles roof code): zinc (#909699 from the air, each roof a little lighter or
    // darker), slate on brick-and-stone, terracotta tile; flat mineral roofs and cities without a code: the tones
    // (zinc #7d8790, M4 critic: #929394 made every mansard's top a big uniform mid-grey plane; flat roofs no darker
    // than #5a5d60, the darkest read as holes in the city from above)
    // (facade.roofs.zinc: the zinc and slate roofs' colour, linear; Berlin's neutral grey slate #86898d and zinc)
    // (facade.roofs.variety, opt-in, Paris: the roofscape as aerials show it rather than one grey carpet. zinc [lo, hi]:
    // each roof's brightness, old dark blue-grey to new silvery zinc, the pale ones that much greyer (silver); slate
    // [share, colour]: that share of the zinc-coded roofs in dark slate (APUR's code is "zinc or slate"); patch: the
    // tone of 7 m patches within a roof (sheets laid in different years, a roof split between owners), faded once
    // they are under a few pixels; verriere: that share of the low flat roofs (courtyard covers under 8 m) glazed;
    // green, terrace: shares of the flat roofs planted (sedum beds) or decked (timber, terracotta tiles); brisis: a
    // mansard's steep slope against its top (0.92 without: the brisis often slate under a zinc top))
    const RV = roofs.variety ? { zinc: [0.7, 1.42], silver: 0.55, slate: [0.15, [0.1, 0.105, 0.118]], patch: 0.06,
      verriere: 0.3, green: 0.05, terrace: 0.06, brisis: 0.86, ...roofs.variety } : null;
    const zincH = h1(seed.mul(83.3));
    const zincTone = RV
      ? mix(vec3(...(roofs.zinc ?? [0.205, 0.242, 0.279])), vec3(0.242, 0.242, 0.242), smoothstep(float(0.55), float(1), zincH).mul(RV.silver))
        .mul(mix(float(RV.zinc[0]), float(RV.zinc[1]), zincH))
      : vec3(...(roofs.zinc ?? [0.205, 0.242, 0.279])).mul(mix(float(0.84), float(1.14), zincH));
    const slateHere = RV ? h1(seed.mul(37.1)).lessThan(RV.slate[0]) : NONE;
    const zincOrSlate = RV ? sel(slateHere, vec3(...RV.slate[1]).mul(mix(float(0.82), float(1.2), h1(seed.mul(13.7)))), zincTone) : zincTone;
    const metalRoof0 = sel(slateMetal, vec3(0.08, 0.1, 0.13), sel(isMon.and(hasRoof), vec3(0.069, 0.08, 0.098), zincOrSlate));   // monuments' mansards: slate #4a5058 (their flat tops zinc)
    // London: no zinc. Welsh slate, blue-grey to purple-grey (region_research.md §4.3: #4d4e4b shade, #776f69 mid,
    // #a1a5a1 sunlit; albedo about #5a5c5e), each roof its own shade; the terraces' flat tops (hidden butterfly
    // roofs behind the parapets) too
    const slateTone = vec3(0.098, 0.1, 0.108).mul(mix(float(0.78), float(1.3), h1(seed.mul(83.3))))
      .add(vec3(0.012, 0.004, 0).mul(h1(seed.mul(19.3))));
    const metalRoof = roofs.slate ? slateTone : metalRoof0;
    // (facade.roofs.tile: the clay tile's colour, linear; Berlin's red tile #a3553a, region_research.md §4.3)
    // (roofs.tileAge: that share of the tile roofs weathered towards brown-grey, each by its own amount)
    const tileRoof = mix(vec3(...(roofs.tile ?? [0.24, 0.16, 0.13])), vec3(0.15, 0.11, 0.09), h1(seed.mul(47.9)).mul(roofs.tileAge ?? 0))
      .mul(mix(float(0.8), float(1.1), h1(seed.mul(83.3))));
    // (no black flat roofs where the tiles carry roof codes (Paris M4: the darkest read as holes in the city from above).
    // Cities without roof codes, New York and Shenzhen, keep their own tones as drawn before them: New York's tar
    // roofs dark, with their grain (an earlier change had kept the lift in every city; the user, 8 Oct: its roofs had turned a
    // lighter, smoother grey than the slopcity copy's, 1197f47))
    const flatRoof0 = roofCodes ? max(roofTone, vec3(0.102, 0.109, 0.117).mul(mix(float(1), float(1.25), h1(seed.mul(29.1))))) : roofTone;
    // (variety: a share of the flat roofs planted, decked or, on low courtyard covers, glazed: pale glass between
    // dark glazing bars every 1.2 m, faded to their mean once finer than a pixel)
    const pwRoof = max(fwidth(positionWorld.x), fwidth(positionWorld.z));
    const flatPick = h1(seed.mul(91.7));
    // (7 m cells per roof, their tone kept to where they are over a few pixels: patches, planters)
    const cellH = RV ? hash2(floor(positionWorld.x.div(7).add(seed.mul(31.7))), floor(positionWorld.z.div(7).add(seed.mul(17.3)))) : null;
    const cellNear = RV ? float(1).sub(smoothstep(float(7 / 6), float(7 / 3), pwRoof)) : null;
    // (green roofs and terraces as beds and decks over part of the roof, never a lawn or one deck: about 60 % of the
    // cells, their mean far away)
    const planted = RV ? mix(float(0.6), f01(cellH.greaterThan(0.4)), cellNear) : null;
    const verriereHere = RV ? hasRoof.not().and(height.lessThan(8)).and(flatPick.lessThan(RV.verriere)) : NONE;
    const glazing = RV ? max(stripe(positionWorld.x.div(1.2), float(0), float(0.07), pwRoof.div(1.2)),
      stripe(positionWorld.z.div(2.4), float(0), float(0.04), pwRoof.div(2.4))) : float(0);
    const flatRoof = RV ? sel(verriereHere, mix(vec3(0.3, 0.335, 0.36), vec3(0.09, 0.095, 0.1), glazing),
      sel(flatPick.greaterThan(float(1 - RV.green)), mix(flatRoof0, vec3(0.08, 0.1, 0.05).mul(mix(float(0.8), float(1.2), h1(seed.mul(17.9)))), planted),
        sel(flatPick.greaterThan(float(1 - RV.green - RV.terrace)), mix(flatRoof0, mix(vec3(0.25, 0.18, 0.125), vec3(0.3, 0.16, 0.1), h1(seed.mul(23.3))), planted),
          flatRoof0))) : flatRoof0;
    // (APUR codes many flat roofs of post-war and modern blocks zinc or slate: without a roof shape they are gravel
    // and bitumen terraces, no standing seams; old buildings' flat tops stay zinc)
    const flatBlock = flatStyles;
    const zincRoof = roofMat.equal(1).and(hasRoof.or(flatBlock.not()));
    const matRoof = sel(zincRoof, metalRoof, sel(roofMat.equal(2), tileRoof, flatRoof));
    // (facade.roofs.flatTops: a roof shape's flat top in the flat roofs' tones, its slopes keeping the tile or slate:
    // Berlin's Berliner Dach, tar paper and gravel behind the tiled front slope)
    // (a number: that share of the roofs, by the seed, the rest's tops in their slopes' tile or slate: Berlin M4 fix round,
    // the Berliner Dach's low courtyard side tiled on many, Kreuzberg's aerials a red-brown carpet)
    const flatTopHere = typeof roofs.flatTops === 'number' ? hasRoof.and(h1(seed.mul(57.7)).lessThan(roofs.flatTops)) : hasRoof;
    const topRoof = roofs.flatTops ? sel(flatTopHere, flatRoof, matRoof) : matRoof;
    // (crowns and spires, a dome's cap included, keep their own colour on top: gilt, lead, copper)
    // zinc tops: standing seams every 0.55 m and each strip's tone within 5 % (faded to their mean far away)
    const seamU = positionWorld.x.add(positionWorld.z).mul(1 / 0.55 / Math.SQRT2);
    const seamW = max(fwidth(seamU), 1e-3);
    const zincTop = roofCodes ? float(1).sub(stripe(seamU, float(0), float(0.1), seamW).mul(0.1))
      .add(hash(floor(seamU).add(seed.mul(71.1))).sub(0.5).mul(0.1).mul(float(1).sub(smoothstep(float(0.3), float(1), seamW)))) : float(1);
    // (variety: 7 m patches within a roof a little lighter or darker, per roof, gone once under a few pixels)
    const patchK = RV ? float(1).add(cellH.sub(0.5).mul(2 * RV.patch).mul(cellNear)) : float(1);
    const topRoofV = RV ? topRoof.mul(patchK) : topRoof;
    const roofColor = sel(isSpire, wallColor, sel(isFactory, sel(blueSteel, vec3(...(roofs.blueTone ?? [0.08, 0.2, 0.42])), vec3(0.42, 0.44, 0.45)),
      sel(isVillage, vec3(0.2, 0.19, 0.17), topRoofV.mul(roofs.slate ? float(1) : sel(zincRoof, zincTop, float(1))))).add(roofNoise));
    // the roof's slopes: a mansard's brisis a shade darker than its top, standing seams (zinc) or courses (tile) close
    // up, and dormers: one per bay on Haussmann blocks and palaces, every other bay elsewhere, a window with pale
    // cheeks in the lower part of the brisis
    const seams = sel(roofs.slate ? roofMat.greaterThan(0.5) : roofMat.equal(2), stripe(y.div(0.32), float(0), float(0.15), fyM.div(0.32)),
      stripe(s.div(0.55), float(0), float(0.08), max(fwidth(s), 1e-3).div(0.55)));
    const slopeMat = matRoof.mul(sel(brisis, float(RV ? RV.brisis : 0.92), float(0.97))).mul(float(1).sub(seams.mul(0.12)));
    const slopeBase = (RV ? slopeMat.mul(patchK) : slopeMat).add(roofNoise);
    const dormerTop = wallH.add(min(roofRise.mul(0.62), float(1.9)));
    const dormerHere = brisis.and(dormersEvery.or(col.mod(2).lessThan(0.5)));
    const dormerY = smoothstep(wallH.add(0.3).sub(fyM), wallH.add(0.3).add(fyM), y).mul(float(1).sub(smoothstep(dormerTop.sub(fyM), dormerTop.add(fyM), y)));
    const dormer = f01(dormerHere).mul(stripe(X, float(0.37), float(0.63), fx)).mul(dormerY);
    const dormerPane = f01(dormerHere).mul(stripe(X, float(0.405), float(0.595), fx))
      .mul(smoothstep(wallH.add(0.45).sub(fyM), wallH.add(0.45).add(fyM), y))
      .mul(float(1).sub(smoothstep(dormerTop.sub(0.3).sub(fyM), dormerTop.sub(0.3).add(fyM), y)));
    const slopeColor = mix(mix(slopeBase, mix(wallColor, vec3(0.42, 0.42, 0.4), 0.5), dormer), vec3(0.03, 0.032, 0.036), dormerPane);
  return { roofColor, slopeColor, zincRoof, blueSteel };
}
