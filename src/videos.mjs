// 植物園導覽影片。影片是按「區」拍的，一區一支。
//
// 要新增一支：在下面的陣列加一行就好，順序就是網站上的顯示順序。
// 區名如果和主檔的「區」一字不差，程式會自動對上，不用另外設定。
// 對不上的（切法不一樣、或主檔沒有這一區）才要寫到 SPECIAL 裡。
//
// 縮圖直接讀 YouTube（i.ytimg.com/vi/<ID>/mqdefault.jpg，320×180），
// 沒有存在網站裡，所以你在 YouTube 換封面，網站會跟著換。
// 標題用小花老師自己的區名，不用 YouTube 標題。

export const VIDEOS = {
  tpbg: [
    { t: '方舟溫室區（上）', v: 'CzXMoRJgwiA' },
    { t: '方舟溫室區（下）', v: 'si5xcgRZ0-w', note: '接續上集' },
    { t: '荷花池', v: '0L7cbn9vZaE' },
    { t: '台灣原生植物區', v: 'US9fKFrO6S8' },
    { t: '澳洲植物區', v: 'TC3ZSEy7f30' },
    { t: '竹區野花園', v: 'lfcVT-4Yv78' },
    { t: '民族植物區', v: 'FrTfx3ZIeBQ' },
    { t: '台灣地名植物館', v: 'A2t5BfkSP5U' },
    { t: '植物名人園區', v: 'Ag2jDXX2Hog' },
    { t: '天南星科區', v: 'yWHgcpce2TA' },
    { t: '多肉植物區', v: 'Z1p2wbIsA0w' },
    { t: '蕨類植物區', v: 'wGVqrx2RIgU' },
    { t: '植物與昆蟲區', v: 'FTO2nu7z5zY' },
    { t: '文學植物區', v: 'PHZP6P-vBwU' },
    { t: '雙子葉植物區', v: 'F_Ew4vAXSCQ' },
    { t: '薑區', v: '_4GTCeSRIII' },
    { t: '棕櫚區', v: 'WvcnvsqjO-U' },
    { t: '水生植物區', v: 'oSk15KLokCA' },
    { t: '佛教植物區', v: 'E71uDSZbI18' },
    { t: '十二生肖區', v: '_neNbf_bhDU' },
    { t: '茜草科區', v: 'rM9n39WRGYc' },
  ],
};

// 首頁那張卡片放哪三支（櫥窗）。要換就改這裡的區名。
export const FEATURED = {
  tpbg: ['方舟溫室區（上）', '台灣原生植物區', '荷花池'],
};

// 主檔的「區」對不上影片標題時，在這裡指定要掛哪幾支。
//   方舟溫室：影片分左右半邊，主檔分四個區，切法不一樣。四個區一律只掛（上），
//            看完的人自己會接著看（下），不必在每一頁都塞兩支。
//   荷花池邊角落野花園：文學植物區歸在這一帶，所以掛荷花池和文學植物區兩支。
const SPECIAL = {
  tpbg: {
    '方舟溫室及蘭房': ['方舟溫室區（上）'],
    '方舟溫室後方': ['方舟溫室區（上）'],
    '方舟溫室左前方': ['方舟溫室區（上）'],
    '方舟溫室右前方': ['方舟溫室區（上）'],
    '荷花池邊角落野花園': ['荷花池', '文學植物區'],
  },
};

export const videosOf = (slug) => VIDEOS[slug] || [];

// 首頁櫥窗那三支；沒設定就拿前三支
export const featuredOf = (slug) => {
  const list = videosOf(slug);
  const names = FEATURED[slug];
  if (!names) return list.slice(0, 3);
  return names.map((n) => list.find((x) => x.t === n)).filter(Boolean);
};

// 這一區有哪幾支導覽影片
export const videosForZone = (slug, z) => {
  const list = videosOf(slug);
  const names = (SPECIAL[slug] || {})[z];
  if (names) return list.filter((x) => names.includes(x.t));
  return list.filter((x) => x.t === z);
};

export const thumbOf = (v) => `https://i.ytimg.com/vi/${v}/mqdefault.jpg`;
export const watchOf = (v) => `https://youtu.be/${v}`;
