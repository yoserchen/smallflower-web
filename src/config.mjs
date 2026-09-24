// 網站設定：要改文字、連結或新增花曆，改這裡就好
export const BRAND = '小花老師的花曆';
export const AUTHOR = '小花老師';
export const DOMAIN = 'smallflower.tw';
export const FB_URL = 'https://www.facebook.com/smallflower.tw';
export const YOUTUBE_URL = 'https://www.youtube.com/@%E5%B0%8F%E8%8A%B1%E8%A6%96%E7%95%8C';        // 小花視界頻道網址，填了才會出現連結
export const SPONSOR_500_URL = '';    // Portaly 500 元方案連結
export const SPONSOR_1000_URL = '';   // Portaly 1000 元方案連結
export const MONTHS = ['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月'];

// 每個花曆一筆。slug 要和 src/data/<slug>.json 同名。
export const CALENDARS = [
  {
    slug: 'tpbg',
    name: '台北植物園花曆',
    place: '台北植物園',
    blurb: '三年來每週進園，記錄每一種花什麼時候開、開在哪裡。',
    intro: '小花老師三年來每週進園拍下的花，依開花月份和位置整理。',
    hasMap: true,
    mapEdition: '2027 年版',
    sheets: { '1': '方舟溫室', '2': '西北', '3': '東側', '4': '南側' },
    note: '月份代表曾在這個月拍到開花，每年實際的花期會前後移動，出發前可以先看 FB 的每週花況。',
  },
  // 之後新增，例如：
  // { slug:'hehuan', name:'合歡山花曆', place:'合歡山', blurb:'…', intro:'…', hasMap:false },
];
