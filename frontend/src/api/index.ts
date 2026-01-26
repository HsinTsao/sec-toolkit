/**
 * API 模块统一导出
 * 
 * 使用方式:
 * import { getNotesApiNotesGet, type NoteResponse } from '@/api'
 * 
 * 或者使用更简洁的别名:
 * import { getNotes, type Note } from '@/api'
 */

// 导出自动生成的 API 函数和类型
export * from './generated'

// ==================== 类型别名（更友好的命名）====================
export type {
  // 用户相关
  UserResponse as User,
  UserCreate,
  UserLogin,
  UserUpdate,
  
  // 认证相关
  Token,
  RefreshTokenRequest,
  
  // 笔记相关
  NoteResponse as Note,
  NoteCreate,
  NoteUpdate,
  CategoryResponse as Category,
  CategoryCreate,
  TagResponse as Tag,
  TagCreate,
  
  // 书签相关
  BookmarkResponse as Bookmark,
  BookmarkCreate,
  BookmarkUpdate,
  UrlMetaResponse as UrlMeta,
  
  // LLM 相关
  LlmProvider,
  LlmConfigResponse as LlmConfig,
  LlmConfigCreate,
  ChatMessage,
  ChatRequest,
  ChatResponse,
  
  // 知识库相关
  KnowledgeItemResponse as KnowledgeItem,
  KnowledgeItemCreate,
  KnowledgeItemUpdate,
  KnowledgeSearchResult,
  
  // 回调服务器相关
  TokenResponse as CallbackToken,
  TokenCreate as CallbackTokenCreate,
  RecordResponse as CallbackRecord,
  PocRuleResponse as PocRule,
  PocRuleCreate,
  PocRuleUpdate,
  
  // 工具相关
  FavoriteResponse as Favorite,
  ToolHistoryResponse as ToolHistory,
} from './generated'

// ==================== API 函数别名（更友好的命名）====================
export {
  // 认证
  loginApiAuthLoginPost as login,
  registerApiAuthRegisterPost as register,
  refreshTokenApiAuthRefreshPost as refreshToken,
  
  // 用户
  getMeApiUsersMeGet as getMe,
  updateMeApiUsersMePatch as updateMe,
  changePasswordApiUsersMePasswordPatch as changePassword,
  
  // 笔记
  getNotesApiNotesGet as getNotes,
  getNoteApiNotesNoteIdGet as getNote,
  createNoteApiNotesPost as createNote,
  updateNoteApiNotesNoteIdPatch as updateNote,
  deleteNoteApiNotesNoteIdDelete as deleteNote,
  getCategoriesApiNotesCategoriesGet as getCategories,
  createCategoryApiNotesCategoriesPost as createCategory,
  deleteCategoryApiNotesCategoriesCategoryIdDelete as deleteCategory,
  getTagsApiNotesTagsGet as getTags,
  createTagApiNotesTagsPost as createTag,
  deleteTagApiNotesTagsTagIdDelete as deleteTag,
  
  // 书签
  getBookmarksApiBookmarksGet as getBookmarks,
  createBookmarkApiBookmarksPost as createBookmark,
  updateBookmarkApiBookmarksBookmarkIdPatch as updateBookmark,
  deleteBookmarkApiBookmarksBookmarkIdDelete as deleteBookmark,
  getUrlMetaApiBookmarksMetaPost as getUrlMeta,
  
  // LLM
  getLlmProvidersApiLlmProvidersGet as getLlmProviders,
  getLlmConfigApiLlmConfigGet as getLlmConfig,
  updateLlmConfigApiLlmConfigPut as updateLlmConfig,
  deleteLlmConfigApiLlmConfigDelete as deleteLlmConfig,
  chatApiLlmChatPost as chat,
  chatStreamApiLlmChatStreamPost as chatStream,
  
  // 知识库
  listKnowledgeItemsApiKnowledgeItemsGet as listKnowledgeItems,
  addKnowledgeItemApiKnowledgeItemsPost as addKnowledgeItem,
  updateKnowledgeItemApiKnowledgeItemsItemIdPatch as updateKnowledgeItem,
  deleteKnowledgeItemApiKnowledgeItemsItemIdDelete as deleteKnowledgeItem,
  searchKnowledgeApiKnowledgeSearchGet as searchKnowledge,
  listFilesApiKnowledgeFilesGet as listFiles,
  uploadFileApiKnowledgeFilesUploadPost as uploadFile,
  deleteFileApiKnowledgeFilesFileIdDelete as deleteFile,
  
  // 回调服务器
  listTokensApiCallbackTokensGet as listCallbackTokens,
  createTokenApiCallbackTokensPost as createCallbackToken,
  deleteTokenApiCallbackTokensTokenIdDelete as deleteCallbackToken,
  renewTokenApiCallbackTokensTokenIdRenewPatch as renewCallbackToken,
  getRecordsApiCallbackTokensTokenIdRecordsGet as getCallbackRecords,
  clearRecordsApiCallbackTokensTokenIdRecordsDelete as clearCallbackRecords,
  pollRecordsApiCallbackTokensTokenIdPollGet as pollCallbackRecords,
  getTokenStatsApiCallbackTokensTokenIdStatsGet as getCallbackTokenStats,
  listPocRulesApiCallbackTokensTokenIdRulesGet as listPocRules,
  createPocRuleApiCallbackTokensTokenIdRulesPost as createPocRule,
  updatePocRuleApiCallbackTokensTokenIdRulesRuleIdPatch as updatePocRule,
  deletePocRuleApiCallbackTokensTokenIdRulesRuleIdDelete as deletePocRule,
  
  // 工具 - 收藏和历史
  getFavoritesApiToolsFavoritesGet as getFavorites,
  addFavoriteApiToolsFavoritesPost as addFavorite,
  removeFavoriteApiToolsFavoritesToolKeyDelete as removeFavorite,
  getHistoryApiToolsHistoryGet as getHistory,
  addHistoryApiToolsHistoryPost as addHistory,
  clearHistoryApiToolsHistoryDelete as clearHistory,
  
  // 工具 - 编码
  base64EncodeApiToolsEncodingBase64EncodePost as base64Encode,
  base64DecodeApiToolsEncodingBase64DecodePost as base64Decode,
  urlEncodeApiToolsEncodingUrlEncodePost as urlEncode,
  urlDecodeApiToolsEncodingUrlDecodePost as urlDecode,
  htmlEncodeApiToolsEncodingHtmlEncodePost as htmlEncode,
  htmlDecodeApiToolsEncodingHtmlDecodePost as htmlDecode,
  hexEncodeApiToolsEncodingHexEncodePost as hexEncode,
  hexDecodeApiToolsEncodingHexDecodePost as hexDecode,
  unicodeEncodeApiToolsEncodingUnicodeEncodePost as unicodeEncode,
  unicodeDecodeApiToolsEncodingUnicodeDecodePost as unicodeDecode,
  
  // 工具 - 哈希
  calculateHashApiToolsHashCalculatePost as calculateHash,
  calculateAllHashesApiToolsHashAllPost as calculateAllHashes,
  
  // 工具 - 加密
  aesEncryptApiToolsCryptoAesEncryptPost as aesEncrypt,
  aesDecryptApiToolsCryptoAesDecryptPost as aesDecrypt,
  rsaGenerateKeysApiToolsCryptoRsaGeneratePost as rsaGenerateKeys,
  rsaEncryptApiToolsCryptoRsaEncryptPost as rsaEncrypt,
  rsaDecryptApiToolsCryptoRsaDecryptPost as rsaDecrypt,
  
  // 工具 - JWT
  jwtDecodeApiToolsJwtDecodePost as jwtDecode,
  jwtEncodeApiToolsJwtEncodePost as jwtEncode,
  jwtVerifyApiToolsJwtVerifyPost as jwtVerify,
  
  // 工具 - 格式化
  formatJsonApiToolsFormatJsonPost as formatJson,
  formatXmlApiToolsFormatXmlPost as formatXml,
  testRegexApiToolsFormatRegexTestPost as testRegex,
  textDiffApiToolsFormatDiffPost as textDiff,
  convertTimestampApiToolsMiscTimestampPost as convertTimestamp,
  baseConvertApiToolsMiscBaseConvertPost as baseConvert,
  generateUuidApiToolsMiscUuidPost as generateUuid,
  
  // 工具 - 网络
  dnsLookupApiToolsNetworkDnsPost as dnsLookup,
  whoisLookupApiToolsNetworkWhoisPost as whoisLookup,
  ipInfoApiToolsNetworkIpInfoPost as ipInfo,
  analyzeTargetApiToolsNetworkAnalyzePost as analyzeTarget,
  
  // 工具 - 密码
  generatePasswordApiToolsPasswordGeneratePost as generatePassword,
  checkPasswordStrengthApiToolsPasswordStrengthPost as checkPasswordStrength,
  
  // Bypass 工具
  urlEncodeApiBypassUrlEncodePost as bypassUrlEncode,
  urlDecodeApiBypassUrlDecodePost as bypassUrlDecode,
  htmlEntityEncodeApiBypassHtmlEncodePost as bypassHtmlEncode,
  htmlDecodeApiBypassHtmlDecodePost as bypassHtmlDecode,
  jsEscapeApiBypassJsEncodePost as bypassJsEncode,
  jsUnescapeApiBypassJsDecodePost as bypassJsDecode,
  caseTransformApiBypassCaseTransformPost as bypassCaseTransform,
  sqlBypassApiBypassSqlBypassPost as bypassSql,
  spaceBypassApiBypassSpaceBypassPost as bypassSpace,
  generateAllApiBypassGenerateAllPost as bypassGenerateAll,
  getTemplatesApiBypassTemplatesGet as getBypassTemplates,
} from './generated'
